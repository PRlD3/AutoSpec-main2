#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def classify(result):
    if result.returncode != 0:
        return "tool_failure"
    if "Pass_" in result.stdout:
        return "passed"
    if "Fail_" in result.stdout or "Invalid" in result.stdout:
        return "tool_failure"
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output/autospec"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--autospec-root", type=Path, default=Path("LLM4Veri"))
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "results.jsonl"
    main_py = args.autospec_root / "main.py"
    rows = []
    for source in sorted(args.input_dir.glob("*.c")):
        target = args.output_dir / source.stem
        target.mkdir(parents=True, exist_ok=True)
        command = ["python", str(main_py), "-f", str(source.resolve()), "-o", str(target.resolve()), "-m", args.model]
        started = datetime.now(timezone.utc).isoformat()
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
            status = classify(completed)
            error = completed.stderr[-4000:]
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = str(exc)
        rows.append({"file": str(source), "status": status, "started_at": started, "error": error})
    result_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    summary = {"total": len(rows), "passed": sum(row["status"] == "passed" for row in rows), "tool_failure": sum(row["status"] == "tool_failure" for row in rows), "timeout": sum(row["status"] == "timeout" for row in rows)}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
