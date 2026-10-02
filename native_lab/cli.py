"""Run a reproducible native job without the web interface."""
import argparse
import json
from pathlib import Path
from native_lab.schema import validate
from native_lab.storage import write_json
from native_lab.worker import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["etch", "ald"], required=True)
    parser.add_argument("--params", type=Path, help="JSON parameter object")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = validate({"model": args.model,
                        "params": json.loads(args.params.read_text(encoding="utf-8")) if args.params else {}})
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "request.json").exists():
        parser.error("Output already contains a run; choose a new directory")
    write_json(args.output / "request.json", payload)
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
