#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import mbpp_to_c


def test_lines(record):
    tests = record.get("test_list", record.get("tests", []))
    if isinstance(tests, str):
        tests = tests.splitlines()
    return [test.strip() for test in tests if test.strip()]


def run_process(command, cwd, timeout):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "exit": None, "stdout": "", "stderr": ""}
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "exit": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_python(code, test, workdir, timeout):
    path = workdir / "case.py"
    path.write_text(code + "\n\n" + test + "\n", encoding="utf-8")
    return run_process([sys.executable, str(path)], workdir, timeout)


def run_c(record, test, workdir, timeout):
    candidate = dict(record)
    candidate["tests"] = [test]
    candidate.pop("test_list", None)
    source = mbpp_to_c.convert_record(candidate, workdir)
    executable = workdir / "case.exe"
    compile_result = run_process(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-pedantic", str(source), "-o", str(executable)],
        workdir,
        timeout,
    )
    if compile_result["status"] != "passed":
        return {"compile": compile_result, "run": None}
    return {"compile": compile_result, "run": run_process([str(executable)], workdir, timeout)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--c-dir", type=Path, default=Path("output/latest_regression"))
    parser.add_argument("--results", type=Path, default=Path("output/differential_results.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("reports/differential_summary.json"))
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    records = mbpp_to_c.load_records(args.input)
    results = []
    tested_tasks = 0
    with tempfile.TemporaryDirectory(prefix="autospec-diff-") as temp:
        root = Path(temp)
        for record in records:
            task_id = mbpp_to_c.safe_task_id(record)
            if not (args.c_dir / f"{task_id}.c").exists():
                continue
            code = mbpp_to_c.select_code(record)
            tests = test_lines(record)
            if not tests:
                continue
            tested_tasks += 1
            for index, test in enumerate(tests):
                case_dir = root / f"{task_id}_{index}"
                case_dir.mkdir()
                python_result = run_python(code, test, case_dir, args.timeout)
                try:
                    c_result = run_c(record, test, case_dir, args.timeout)
                except Exception as error:
                    c_result = {"compile": {"status": "conversion_error", "error": str(error)}, "run": None}
                c_run = c_result.get("run")
                c_status = c_run.get("status") if c_run else c_result["compile"].get("status")
                status = "matched" if python_result["status"] == "passed" and c_status == "passed" else "mismatch"
                results.append({
                    "task_id": task_id,
                    "case_id": f"test_{index}",
                    "test": test,
                    "status": status,
                    "python": python_result,
                    "c": c_result,
                })
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in results) + ("\n" if results else ""), encoding="utf-8")
    matched = sum(item["status"] == "matched" for item in results)
    summary = {
        "tasks": tested_tasks,
        "cases": len(results),
        "matched": matched,
        "mismatched": len(results) - matched,
        "match_rate": round(matched / len(results) * 100, 1) if results else 0.0,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
