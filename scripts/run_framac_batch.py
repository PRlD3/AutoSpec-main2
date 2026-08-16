import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run_case(source, timeout):
    absolute_source = source.resolve()
    drive = absolute_source.drive.rstrip(":\\/").lower()
    linux_source = "/mnt/" + drive + str(absolute_source)[len(absolute_source.drive):].replace("\\", "/")
    command = [
        "wsl",
        "-d",
        "Ubuntu",
        "--",
        "opam",
        "exec",
        "--switch=5.1.1",
        "--",
        "frama-c",
        "-wp",
        "-wp-prover",
        "z3",
        "-wp-timeout",
        "10",
        linux_source,
    ]
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "file": source.name,
            "status": "timeout",
            "started_at": started,
            "returncode": None,
            "proved": None,
            "goals": None,
            "stdout": str(exc.stdout or "")[-4000:],
            "stderr": str(exc.stderr or "")[-4000:],
        }
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    output = stdout + "\n" + stderr
    match = re.search(r"Proved goals:\s*(\d+)\s*/\s*(\d+)", output)
    if result.returncode != 0:
        status = "tool_failure"
    elif not match:
        status = "unknown"
    elif match.group(1) == match.group(2):
        status = "proved"
    else:
        status = "partial"
    return {
        "file": source.name,
        "status": status,
        "started_at": started,
        "returncode": result.returncode,
        "proved": int(match.group(1)) if match else None,
        "goals": int(match.group(2)) if match else None,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    excluded = set(args.exclude)
    sources = [
        source
        for source in sorted(args.input_dir.glob("*.c"))
        if source.name not in excluded
    ]
    rows = [run_case(source, args.timeout) for source in sources]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    summary = {
        "total": len(rows),
        "proved": sum(row["status"] == "proved" for row in rows),
        "partial": sum(row["status"] == "partial" for row in rows),
        "tool_failure": sum(row["status"] == "tool_failure" for row in rows),
        "timeout": sum(row["status"] == "timeout" for row in rows),
        "unknown": sum(row["status"] == "unknown" for row in rows),
    }
    summary_path = args.output.with_name("framac_summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
