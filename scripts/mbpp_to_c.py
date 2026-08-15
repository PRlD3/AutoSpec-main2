#!/usr/bin/env python3
import argparse
import ast
import json
import re
from pathlib import Path


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


def value_type(value):
    if isinstance(value, bool):
        return "int"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    return None


def expression(node, list_names=None):
    list_names = list_names or set()
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "1" if node.value else "0"
        if node.value is None:
            return "0"
        if isinstance(node.value, str):
            raise ValueError("字符串表达式未实现")
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.List):
        values = ", ".join(expression(item, list_names) for item in node.elts)
        return f"make_int_list((int[]){{{values}}}, {len(node.elts)})"
    if isinstance(node, ast.Subscript):
        return f"{expression(node.value, list_names)}.data[{expression(node.slice, list_names)}]"
    if isinstance(node, ast.BinOp):
        operators = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "/", ast.Mod: "%"}
        operator = operators.get(type(node.op))
        if not operator:
            raise ValueError("不支持的二元运算")
        return f"({expression(node.left, list_names)} {operator} {expression(node.right, list_names)})"
    if isinstance(node, ast.UnaryOp):
        operators = {ast.USub: "-", ast.UAdd: "+", ast.Not: "!"}
        operator = operators.get(type(node.op))
        if not operator:
            raise ValueError("不支持的一元运算")
        return f"{operator}{expression(node.operand, list_names)}"
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        operators = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
        operator = operators.get(type(node.ops[0]))
        if not operator:
            raise ValueError("不支持的比较运算")
        return f"({expression(node.left, list_names)} {operator} {expression(node.comparators[0], list_names)})"
    if isinstance(node, ast.BoolOp) and len(node.values) >= 2:
        operator = " && " if isinstance(node.op, ast.And) else " || "
        return "(" + operator.join(expression(item, list_names) for item in node.values) + ")"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len" and len(node.args) == 1:
        return f"{expression(node.args[0], list_names)}.length"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "abs" and len(node.args) == 1:
        return f"abs({expression(node.args[0], list_names)})"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = ", ".join(expression(arg, list_names) for arg in node.args)
        return f"{node.func.id}({args})"
    raise ValueError(f"不支持的表达式: {ast.dump(node, include_attributes=False)}")


def range_expression(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "range":
        raise ValueError("for 循环目前只支持 range")
    if not 1 <= len(node.args) <= 3:
        raise ValueError("range 参数数量不支持")
    values = [expression(arg) for arg in node.args]
    if len(values) == 1:
        return "0", values[0], "1"
    if len(values) == 2:
        return values[0], values[1], "1"
    return values[0], values[1], values[2]


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
        value = expression(node.value, list_names)
        if target in declared:
            return [f"{prefix}{target} = {value};"]
        declared.add(target)
        if isinstance(node.value, ast.List):
            list_names.add(target)
            return [f"{prefix}IntList {target} = {value};"]
        return [f"{prefix}int {target} = {value};"]
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
        start, stop, step = range_expression(node.iter)
        target = node.target.id
        if target not in declared:
            declared.add(target)
        condition = f"{target} < {stop}" if step == "1" else f"{target} > {stop}"
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


def convert_record(record, output_dir):
    solution = record.get("solutions", {}).get("no_tests", {})
    code = solution.get("code", record.get("code", ""))
    task_id = str(record.get("task_id", record.get("id", record.get("key", "unknown"))))
    if not code:
        raise ValueError("缺少 code 字段")
    tree = ast.parse(code)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        raise ValueError("每条记录必须包含一个顶层函数")
    function = functions[0]
    list_args = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            list_args.add(node.value.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len" and node.args and isinstance(node.args[0], ast.Name):
            list_args.add(node.args[0].id)
    args = ", ".join(f"IntList {arg.arg}" if arg.arg in list_args else f"int {arg.arg}" for arg in function.args.args)
    lines = ["#include <assert.h>", "#include <stdlib.h>", "", "typedef struct { int *data; int length; } IntList;", "", "static IntList make_int_list(int *data, int length) { return (IntList){data, length}; }", "", f"int {function.name}({args}) {{"]
    declared = {arg.arg for arg in function.args.args}
    list_names = set(list_args)
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
        task_id = str(record.get("task_id", record.get("id", record.get("key", "unknown")))) if isinstance(record, dict) else "unknown"
        try:
            convert_record(record, args.output_dir)
            converted += 1
        except Exception as error:
            failures.append({"task_id": task_id, "reason": str(error)})
    args.failures.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in failures) + ("\n" if failures else ""), encoding="utf-8")
    print(json.dumps({"total": converted + len(failures), "converted": converted, "failed": len(failures)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
