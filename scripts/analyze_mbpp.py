#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


def load_records(path):
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "records", "examples", "tasks"):
            if isinstance(data.get(key), list):
                return data[key]
        if all(isinstance(value, dict) for value in data.values()):
            return list(data.values())
    raise ValueError("JSON 顶层必须是数组，或包含 data/records/examples/tasks 数组")


def analyze(records):
    key_counts = Counter()
    types = Counter()
    for record in records:
        if not isinstance(record, dict):
            types[type(record).__name__] += 1
            continue
        key_counts.update(record.keys())
        types["object"] += 1
    return {
        "total_records": len(records),
        "object_records": types.get("object", 0),
        "record_types": dict(types),
        "field_counts": dict(key_counts),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/mbpp_dataset_analysis.json"))
    args = parser.parse_args()
    result = analyze(load_records(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
