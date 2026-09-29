"""Compare browser-exported runs/sweeps with the native Python implementation.

Usage: python sim_app/verify_browser_export.py path/to/run.json [more.json ...]
This checks numerical portability, not agreement with physical equipment.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim_app.service import simulate_request, sweep_request


def compare(actual: Any, expected: Any, path: str = "result") -> int:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise AssertionError(f"{path}: categorical value mismatch")
        return 0
    if isinstance(expected, (float, int)):
        if isinstance(actual, bool) or not isinstance(actual, (float, int)):
            raise AssertionError(f"{path}: expected a number")
        if not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-9):
            raise AssertionError(f"{path}: {actual!r} != {expected!r}")
        return 1
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError(f"{path}: array length mismatch")
        return sum(compare(a, b, f"{path}[{i}]") for i, (a, b) in enumerate(zip(actual, expected)))
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise AssertionError(f"{path}: field mismatch")
        return sum(compare(actual[key], value, f"{path}.{key}") for key, value in expected.items())
    raise TypeError(f"{path}: unsupported comparison type {type(expected).__name__}")


def verify(path: Path) -> dict:
    actual = json.loads(path.read_text(encoding="utf-8"))
    if actual.get("execution_environment", {}).get("engine") != "Pyodide":
        raise ValueError(f"{path.name}: not a browser Python export")
    payload = {key: actual[key] for key in ("model", "params", "fault")}
    if "runs" in actual:
        payload.update(parameter=actual["parameter"], values=[row["input"] for row in actual["runs"]])
        expected = sweep_request(payload)
        fields = ("model_version", "parameter", "unit", "runs")
    else:
        expected = simulate_request(payload)
        fields = ("run_id", "result", "baseline")
    scalars = sum(compare(actual[key], expected[key], key) for key in fields)
    return {"file": path.name, "model": actual["model"], "fault": actual["fault"],
            "numeric_values_compared": scalars, "result": "PASS",
            "browser_environment": actual["execution_environment"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", nargs="+", type=Path)
    args = parser.parse_args()
    report = {"rtol": 1e-7, "atol": 1e-9, "native_python": sys.version.split()[0],
              "comparisons": [verify(path) for path in args.exports]}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
