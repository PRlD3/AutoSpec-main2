#!/usr/bin/env python3
import argparse
import ast
import json
import re
from pathlib import Path


_allowed_calls = set()


def load_records(path):
    text = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, list):
        return data
    for key in ("data", "records", "examples", "tasks"):
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return data[key]
    if isinstance(data, dict) and all(isinstance(value, dict) for value in data.values()):
        return list(data.values())
    raise ValueError("JSON 顶层必须是数组，或包含 data/records/examples/tasks 数组")


def safe_task_id(record):
    raw = str(record.get("task_id", record.get("id", record.get("key", "unknown"))))
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._") or "unknown"


def value_type(value):
    if isinstance(value, bool):
        return "int"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    return None


def expression_type(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, float):
        return "double"
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Div):
            return "double"
        if expression_type(node.left) == "double" or expression_type(node.right) == "double":
            return "double"
    if isinstance(node, ast.UnaryOp):
        return expression_type(node.operand)
    return "int"


def return_type(function):
    return "double" if any(expression_type(node.value) == "double" for node in ast.walk(function) if isinstance(node, ast.Return)) else "int"


def is_list_expression(node):
    return isinstance(node, (ast.List, ast.ListComp)) or (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)) or (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sorted")


def is_list_value(node, list_names):
    if isinstance(node, ast.Name):
        return node.id in list_names
    if is_list_expression(node):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id == "sorted" and len(node.args) == 1
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return is_list_value(node.left, list_names) or is_list_value(node.right, list_names)
    return False


def expression(node, list_names=None, substitutions=None):
    list_names = list_names or set()
    substitutions = substitutions or {}
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "1" if node.value else "0"
        if node.value is None:
            return "0"
        if isinstance(node.value, str):
            raise ValueError("字符串表达式未实现")
        return repr(node.value)
    if isinstance(node, ast.Name):
        return substitutions.get(node.id, node.id)
    if isinstance(node, ast.List):
        if any(isinstance(item, (ast.List, ast.Tuple, ast.Dict, ast.Set)) for item in node.elts):
            raise ValueError("不支持嵌套或复合类型列表")
        values = ", ".join(expression(item, list_names) for item in node.elts)
        return f"make_int_list((int[]){{{values}}}, {len(node.elts)})"
    if isinstance(node, ast.ListComp):
        raise ValueError("列表推导式需要在赋值语句中处理")
    if isinstance(node, ast.Subscript):
        value = expression(node.value, list_names)
        if isinstance(node.slice, ast.Slice):
            if node.slice.lower is None or node.slice.upper is None or node.slice.step is not None:
                raise ValueError("列表切片目前需要 start、stop 且不支持 step")
            start = expression(node.slice.lower, list_names)
            stop = expression(node.slice.upper, list_names)
            return f"slice_int_list({value}, {start}, {stop})"
        return f"{value}.data[{expression(node.slice, list_names)}]"
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add) and (is_list_value(node.left, list_names) or is_list_value(node.right, list_names)):
            raise ValueError("不支持列表拼接：需要实现 IntList 连接语义")
        operators = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "/", ast.Mod: "%"}
        operator = operators.get(type(node.op))
        if not operator:
            raise ValueError("不支持的二元运算")
        left = expression(node.left, list_names, substitutions)
        right = expression(node.right, list_names, substitutions)
        if isinstance(node.op, ast.Div):
            return f"((double)({left}) / ({right}))"
        return f"({left} {operator} {right})"
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not) and is_list_value(node.operand, list_names):
            raise ValueError("不支持列表真值判断：需要定义空列表与非空列表语义")
        operators = {ast.USub: "-", ast.UAdd: "+", ast.Not: "!"}
        operator = operators.get(type(node.op))
        if not operator:
            raise ValueError("不支持的一元运算")
        return f"{operator}{expression(node.operand, list_names, substitutions)}"
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        if is_list_value(node.left, list_names) or is_list_value(node.comparators[0], list_names):
            raise ValueError("不支持列表比较：需要实现按元素比较语义")
        operators = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
        operator = operators.get(type(node.ops[0]))
        if not operator:
            raise ValueError("不支持的比较运算")
        return f"({expression(node.left, list_names, substitutions)} {operator} {expression(node.comparators[0], list_names, substitutions)})"
    if isinstance(node, ast.BoolOp) and len(node.values) >= 2:
        operator = " && " if isinstance(node.op, ast.And) else " || "
        return "(" + operator.join(expression(item, list_names) for item in node.values) + ")"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len" and len(node.args) == 1:
        return f"{expression(node.args[0], list_names)}.length"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "abs" and len(node.args) == 1:
        return f"abs({expression(node.args[0], list_names)})"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"sum", "min", "max"} and len(node.args) == 1:
        return f"{node.func.id}_int_list({expression(node.args[0], list_names)})"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"min", "max"} and len(node.args) >= 2:
        values = [expression(arg, list_names) for arg in node.args]
        operator = "<" if node.func.id == "min" else ">"
        result = values[0]
        for value in values[1:]:
            result = f"(({result}) {operator} ({value}) ? ({result}) : ({value}))"
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int" and len(node.args) == 1:
        return f"((int)({expression(node.args[0], list_names)}))"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sorted" and len(node.args) == 1:
        return f"sorted_int_list({expression(node.args[0], list_names)})"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in _allowed_calls:
            args = ", ".join(expression(arg, list_names) for arg in node.args)
            return f"{node.func.id}({args})"
        raise ValueError(f"不支持的函数调用: {ast.unparse(node)}")
    raise ValueError(f"不支持的表达式: {ast.dump(node, include_attributes=False)}")


def range_expression(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "range":
        raise ValueError("for 循环目前只支持 range")
    if not 1 <= len(node.args) <= 3:
        raise ValueError("range 参数数量不支持")
    values = [expression(arg) for arg in node.args]
    if len(values) == 1:
        return "0", values[0], "1", "<"
    if len(values) == 2:
        return values[0], values[1], "1", "<"
    step = node.args[2]
    if isinstance(step, ast.Constant) and isinstance(step.value, (int, float)):
        if step.value == 0:
            raise ValueError("range 步长不能为 0")
        operator = ">" if step.value < 0 else "<"
        return values[0], values[1], values[2], operator
    raise ValueError("range 目前只支持常量步长")


def statement(node, indent, declared, list_names):
    prefix = "    " * indent
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        return []
    if isinstance(node, ast.Pass):
        return []
    if isinstance(node, ast.Return):
        return [f"{prefix}return {expression(node.value, list_names)};"]
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        target = node.targets[0].id
        if isinstance(node.value, ast.ListComp):
            if len(node.value.generators) != 1 or node.value.generators[0].ifs or not isinstance(node.value.generators[0].target, ast.Name) or not isinstance(node.value.generators[0].iter, ast.Name):
                raise ValueError("列表推导式目前只支持单个列表来源且不带条件")
            generator = node.value.generators[0]
            source = expression(generator.iter, list_names)
            variable = generator.target.id
            value = expression(node.value.elt, list_names, {variable: f"{source}.data[i]"})
            list_names.add(target)
            return [f"{prefix}{target} = make_empty_int_list();", f"{prefix}for (int i = 0; i < {source}.length; i++) {{", f"{prefix}    append_int_list(&{target}, {value});", f"{prefix}}}"]
        value = expression(node.value, list_names)
        if target in declared:
            return [f"{prefix}{target} = {value};"]
        if isinstance(node.value, (ast.List, ast.Subscript, ast.ListComp)) and (isinstance(node.value, (ast.List, ast.ListComp)) or isinstance(node.value.slice, ast.Slice)):
            list_names.add(target)
            return [f"{prefix}{target} = {value};"]
        return [f"{prefix}{target} = {value};"]
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "append" and len(node.value.args) == 1:
        if not isinstance(node.value.func.value, ast.Name):
            raise ValueError("append 目前只支持变量列表")
        return [f"{prefix}append_int_list(&{node.value.func.value.id}, {expression(node.value.args[0], list_names)});"]
    if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
        operators = {ast.Add: "+=", ast.Sub: "-=", ast.Mult: "*=", ast.Div: "/=", ast.Mod: "%="}
        operator = operators.get(type(node.op))
        if not operator:
            raise ValueError("不支持的复合赋值")
        return [f"{prefix}{node.target.id} {operator} {expression(node.value, list_names)};"]
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Name) and node.value.func.id == "assert" and len(node.value.args) == 1:
            return [f"{prefix}assert({expression(node.value.args[0], list_names)});"]
    if isinstance(node, ast.If) and len(node.orelse) == 0:
        lines = [f"{prefix}if ({expression(node.test, list_names)}) {{"]
        for child in node.body:
            lines.extend(statement(child, indent + 1, declared, list_names))
        lines.append(f"{prefix}}}")
        return lines
    if isinstance(node, ast.If):
        lines = [f"{prefix}if ({expression(node.test, list_names)}) {{"]
        for child in node.body:
            lines.extend(statement(child, indent + 1, declared, list_names))
        lines.append(f"{prefix}}} else {{")
        for child in node.orelse:
            lines.extend(statement(child, indent + 1, declared, list_names))
        lines.append(f"{prefix}}}")
        return lines
    if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
        start, stop, step, operator = range_expression(node.iter)
        target = node.target.id
        if target not in declared:
            declared.add(target)
        condition = f"{target} {operator} {stop}"
        lines = [f"{prefix}for (int {target} = {start}; {condition}; {target} += {step}) {{"]
        for child in node.body:
            lines.extend(statement(child, indent + 1, declared, list_names))
        lines.append(f"{prefix}}}")
        if node.orelse:
            raise ValueError("for...else 未实现")
        return lines
    if isinstance(node, ast.While):
        lines = [f"{prefix}while ({expression(node.test, list_names)}) {{"]
        for child in node.body:
            lines.extend(statement(child, indent + 1, declared, list_names))
        lines.append(f"{prefix}}}")
        if node.orelse:
            raise ValueError("while...else 未实现")
        return lines
    if isinstance(node, (ast.Break, ast.Continue)):
        return [f"{prefix}{'break' if isinstance(node, ast.Break) else 'continue'};"]
    raise ValueError(f"不支持的语句: {ast.dump(node, include_attributes=False)}")


def local_declarations(function):
    declarations = {}
    arguments = {arg.arg for arg in function.args.args}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if target not in arguments and target not in declarations:
                declarations[target] = "IntList" if is_list_expression(node.value) else "int"
    return declarations


def select_code(record):
    solutions = record.get("solutions", {})
    with_tests = solutions.get("with_tests", {})
    if with_tests.get("verifier_status") == "SUCCESS" and with_tests.get("code"):
        return with_tests["code"]
    latest = record.get("latest_generation", {})
    if latest.get("stage") == "with_tests" and latest.get("code"):
        return latest["code"]
    if latest.get("code"):
        return latest["code"]
    no_tests = solutions.get("no_tests", {})
    if no_tests.get("code"):
        return no_tests["code"]
    if record.get("code"):
        return record["code"]
    raise ValueError("缺少可用 code 字段")


def convert_record(record, output_dir):
    global _allowed_calls
    code = select_code(record)
    task_id = safe_task_id(record)
    if not code:
        raise ValueError("缺少 code 字段")
    tree = ast.parse(code)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        raise ValueError("每条记录必须包含一个顶层函数")
    function = functions[0]
    _allowed_calls = {function.name}
    for node in ast.walk(function):
        if isinstance(node, ast.List) and any(isinstance(item, (ast.List, ast.Tuple, ast.Dict, ast.Set)) for item in node.elts):
            raise ValueError("不支持嵌套或复合类型列表")
    list_args = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            list_args.add(node.value.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len" and node.args and isinstance(node.args[0], ast.Name):
            list_args.add(node.args[0].id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append" and isinstance(node.func.value, ast.Name):
            list_args.add(node.func.value.id)
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            list_args.add(node.iter.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"sum", "min", "max", "sorted"} and len(node.args) == 1 and isinstance(node.args[0], ast.Name):
            list_args.add(node.args[0].id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sorted" and len(node.args) == 1:
            for child in ast.walk(node.args[0]):
                if isinstance(child, ast.Name):
                    list_args.add(child.id)
    args = ", ".join(f"IntList {arg.arg}" if arg.arg in list_args else f"int {arg.arg}" for arg in function.args.args)
    function_return_type = return_type(function)
    lines = ["#include <assert.h>", "#include <stdlib.h>", "", "typedef struct { int *data; int length; int capacity; } IntList;", "", "/*@ ensures \\result.data != \\null; ensures \\result.length == 0; ensures \\result.capacity == 4; */", "static IntList make_empty_int_list(void) { int *data = malloc(sizeof(int) * 4); if (data == NULL) abort(); return (IntList){data, 0, 4}; }", "/*@ requires length >= 0; requires length <= 1073741823; requires length == 0 || \\valid_read(data + (0 .. length - 1)); */", "static IntList make_int_list(int *data, int length) { IntList result = make_empty_int_list(); while (result.capacity < length) { if (result.capacity > 1073741823) abort(); int next_capacity = result.capacity * 2; int *next_data = realloc(result.data, sizeof(int) * next_capacity); if (next_data == NULL) abort(); result.data = next_data; result.capacity = next_capacity; } for (int i = 0; i < length; i++) result.data[i] = data[i]; result.length = length; return result; }", "/*@ requires list != \\null; requires list->data != \\null; requires 0 <= list->length <= list->capacity; requires list->capacity <= 1073741823; requires \\valid(list->data + (0 .. list->capacity - 1)); assigns list->data, list->length, list->capacity; ensures list->length == \\old(list->length) + 1; ensures list->capacity >= \\old(list->capacity); */", "static void append_int_list(IntList *list, int value) { if (list->length == list->capacity) { if (list->capacity > 1073741823) abort(); int next_capacity = list->capacity * 2; int *next_data = realloc(list->data, sizeof(int) * next_capacity); if (next_data == NULL) abort(); list->data = next_data; list->capacity = next_capacity; } list->data[list->length++] = value; }", "static int sum_int_list(IntList list) { int result = 0; for (int i = 0; i < list.length; i++) result += list.data[i]; return result; }", "static int min_int_list(IntList list) { if (list.length <= 0) return 0; int result = list.data[0]; for (int i = 1; i < list.length; i++) if (list.data[i] < result) result = list.data[i]; return result; }", "static int max_int_list(IntList list) { if (list.length <= 0) return 0; int result = list.data[0]; for (int i = 1; i < list.length; i++) if (list.data[i] > result) result = list.data[i]; return result; }", "static IntList slice_int_list(IntList list, int start, int stop) { if (start < 0) start = 0; if (stop > list.length) stop = list.length; if (stop < start) stop = start; return make_int_list(list.data + start, stop - start); }", "static IntList sorted_int_list(IntList list) { IntList result = make_int_list(list.data, list.length); for (int i = 0; i < result.length; i++) for (int j = i + 1; j < result.length; j++) if (result.data[j] < result.data[i]) { int t = result.data[i]; result.data[i] = result.data[j]; result.data[j] = t; } return result; }", "", f"int {function.name}({args}) {{"]
    lines = [line.replace(f"int {function.name}(", f"{function_return_type} {function.name}(", 1) for line in lines]
    local_types = local_declarations(function)
    declared = {arg.arg for arg in function.args.args} | set(local_types)
    list_names = set(list_args)
    declaration_lines = [f"    {local_types[name]} {name};" for name in local_types]
    lines.extend(declaration_lines)
    for node in function.body:
        lines.extend(statement(node, 1, declared, list_names))
    if not function.body or not isinstance(function.body[-1], ast.Return):
        raise ValueError("函数必须以 return 结束")
    lines.append("}")
    tests = record.get("test_list", record.get("tests", []))
    if isinstance(tests, str):
        tests = [line for line in tests.splitlines() if line.strip()]
    for test in tests:
        match = re.search(r"^\s*assert\s+(.+?)\s*$", test)
        if match:
            assertion = match.group(1)
            if assertion.startswith("(") and assertion.endswith(")"):
                assertion = assertion[1:-1]
            assertion_code = expression(ast.parse(assertion, mode="eval").body, list_names)
            lines.append(f"\nint main(void) {{\n    assert({assertion_code});\n    return 0;\n}}")
            break
    path = output_dir / f"{task_id}.c"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output/converted"))
    parser.add_argument("--failures", type=Path, default=Path("reports/conversion_failures.jsonl"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.failures.parent.mkdir(parents=True, exist_ok=True)
    failures = []
    converted = 0
    for record in load_records(args.input):
        task_id = safe_task_id(record) if isinstance(record, dict) else "unknown"
        try:
            convert_record(record, args.output_dir)
            converted += 1
        except Exception as error:
            failures.append({"task_id": task_id, "reason": str(error)})
    args.failures.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in failures) + ("\n" if failures else ""), encoding="utf-8")
    print(json.dumps({"total": converted + len(failures), "converted": converted, "failed": len(failures)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
