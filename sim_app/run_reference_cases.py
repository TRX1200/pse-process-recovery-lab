"""Export reproducible baseline, fault and intervention cases without the web UI."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim_app.server import simulate_request


CASES = [
    ("ald_baseline", {"model": "ald", "fault": "none"}),
    ("ald_purge_restriction", {"model": "ald", "fault": "purge_restriction"}),
    ("ald_longer_purge", {"model": "ald", "fault": "purge_restriction",
                           "params": {"purge_a_s": 6, "purge_b_s": 6}}),
    ("etch_baseline", {"model": "etch", "fault": "none"}),
    ("etch_rf_mismatch", {"model": "etch", "fault": "rf_mismatch"}),
    ("etch_delivery_restored", {"model": "etch", "fault": "rf_mismatch",
                                "params": {"fault_severity": 0}}),
]


def run(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, request in CASES:
        result = simulate_request(request)
        (out / f"{name}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for metric in result["result"]["metrics"]:
            rows.append({"case": name, "run_id": result["run_id"], "metric": metric["key"],
                         "value": metric["value"], "unit": metric["unit"]})
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "README.md").write_text(
        "# Reference model cases\n\n"
        "These are reproducible numerical scenarios, not experimental measurements.\n\n"
        "ALD: compare normal operation, restricted purge evacuation, and longer purge "
        "with the same restriction still present. Examine both gas overlap and cycle time. "
        "Total thickness is a first-cycle-times-N projection, especially uncertain when residues remain.\n\n"
        "Etch: compare normal operation, reflected-power fault, and restoring the "
        "injected fault severity to zero. Restoration represents a known model-state "
        "intervention, not an independently diagnosed or physically performed repair.\n\n"
        "The model version, all requested parameters and effective internal state are in each JSON.\n",
        encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("outputs/process_studio/reference_cases"))
    args = parser.parse_args()
    rows = run(args.out)
    print(json.dumps({"output": str(args.out.resolve()), "cases": len(CASES), "metric_rows": len(rows)}))


if __name__ == "__main__":
    main()
