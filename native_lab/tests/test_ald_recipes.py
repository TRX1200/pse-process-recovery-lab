"""Check experiment isolation and the published input contract without a solver."""
import csv
import json
from pathlib import Path
import unittest

from native_lab.ald_recipes import catalog
from native_lab.sequence_schema import FIELDS, validate_sequence


class ALDRecipeTests(unittest.TestCase):
    def test_complete_valid_independent_inputs(self):
        data = catalog()
        recipes = data["recipes"]
        self.assertEqual(len(recipes), 10)
        self.assertEqual(len({r["id"] for r in recipes}), 10)
        expected_keys = {f["key"] for f in FIELDS}
        for recipe in recipes:
            self.assertEqual(set(recipe["request"]["params"]), expected_keys)
            self.assertEqual(validate_sequence(recipe["request"]), recipe["request"])
            self.assertNotIn("frames", recipe)
            self.assertNotIn("metrics", recipe)
        recipes[0]["request"]["params"]["seed"] = 1
        self.assertEqual(recipes[1]["request"]["params"]["seed"], 20261003)
        self.assertEqual(catalog()["recipes"][0]["request"]["params"]["seed"], 20261003)

    def test_controlled_comparisons_and_matched_exposure(self):
        recipes = {r["id"]: r for r in catalog()["recipes"]}
        expected = {"D02": {"pulse_s"}, "D03": {"pulse_s"}, "D04": {"pressure_pa"},
                    "D05": {"pressure_pa"}, "D06": {"cycles"}, "D07": {"cycles"},
                    "D08": {"pressure_pa", "pulse_s"}, "D09": {"width_nm"}, "D10": {"pulse_s"}}
        for key, fields in expected.items():
            recipe = recipes[key]
            reference = recipes[recipe["compare_to"]]["request"]["params"]
            actual = {k for k, v in recipe["request"]["params"].items() if reference[k] != v}
            self.assertEqual(actual, fields)
            self.assertEqual(set(recipe["changed_keys"]), fields)
        self.assertEqual(recipes["D10"]["compare_to"], "D09")
        a, b = (recipes[k]["request"]["params"] for k in ("D01", "D08"))
        self.assertAlmostEqual(a["pressure_pa"] * a["pulse_s"], b["pressure_pa"] * b["pulse_s"])

    def test_published_json_and_csv_match_source(self):
        root = Path(__file__).resolve().parents[2] / "sim_app/frontend/public/native"
        data = json.loads((root / "ald-recipes.json").read_text(encoding="utf-8"))
        self.assertEqual(data, catalog())
        with (root / "ald-experiments.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 10)
        for row, recipe in zip(rows, data["recipes"]):
            self.assertEqual(row["id"], recipe["id"])
            self.assertEqual(row["compare_to"], recipe["compare_to"] or "")
            for key, value in recipe["request"]["params"].items():
                self.assertEqual(float(row[key]), value)
