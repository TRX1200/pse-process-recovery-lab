import math
import sys
import unittest
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_day1 import generate


class DayOneTests(unittest.TestCase):
    def test_reproducible_but_seed_changes_observations(self):
        self.assertEqual(generate(7), generate(7))
        self.assertNotEqual(generate(7)["etch"], generate(8)["etch"])

    def test_truth_is_separate_and_complete(self):
        data = generate(7)
        self.assertNotIn("injected_state", data["etch"][0])
        self.assertNotIn("is_doi", data["candidates"][0])
        self.assertEqual({r["wafer_id"] for r in data["etch"]}, {r["wafer_id"] for r in data["etch_truth"]})
        self.assertEqual({r["candidate_id"] for r in data["candidates"]}, {r["candidate_id"] for r in data["labels"]})

    def test_case_b_is_monitor_only_not_process_change(self):
        rows = generate(7)["etch"]
        base = [r for r in rows if r["case_id"] == "BASELINE"]
        case = [r for r in rows if r["case_id"] == "CASE_B"]
        self.assertGreater(mean(r["pressure_readback_mtorr"]-r["pressure_reference_mtorr"] for r in case), 1.0)
        self.assertLess(abs(mean(r["etch_rate_nm_min"] for r in case)-mean(r["etch_rate_nm_min"] for r in base)), 1.0)

    def test_wafer_split_has_no_overlap(self):
        rows = generate(7)["candidates"]
        groups = {s: {r["wafer_id"] for r in rows if r["split"] == s} for s in ("train", "validation", "test")}
        self.assertFalse(groups["train"] & groups["validation"])
        self.assertFalse(groups["train"] & groups["test"])
        self.assertFalse(groups["validation"] & groups["test"])

    def test_finite_values_and_unique_identifiers(self):
        data = generate(7)
        for rows in data.values():
            for row in rows:
                self.assertTrue(all(math.isfinite(v) for v in row.values() if isinstance(v, (int,float))))
        ids = [r["candidate_id"] for r in data["candidates"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_invalid_seed(self):
        for value in (-1, 1.5, True, "7"):
            with self.assertRaises(ValueError):
                generate(value)


if __name__ == "__main__":
    unittest.main()
