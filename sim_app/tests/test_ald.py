"""Limiting cases and numerical checks for the educational ALD model."""

import json
import math
import unittest

import numpy as np

from sim_app.models.ald import PARAMS, _solve_cycle, _validate, simulate


def metric(result, key):
    return next(item["value"] for item in result["metrics"] if item["key"] == key)


class AldModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = simulate({})

    def test_json_contract_and_finite_values(self):
        json.dumps(self.baseline, allow_nan=False)
        self.assertEqual(self.baseline["spatial"]["kind"], "ald")
        for series in self.baseline["series"]:
            self.assertTrue(np.all(np.diff(series["x"]) > 0))
            for line in series["lines"]:
                self.assertEqual(len(line["values"]), len(series["x"]))
                self.assertTrue(np.isfinite(line["values"]).all())

    def test_zero_reactant_dose_gives_zero_growth(self):
        for key in ("pressure_a_pa", "pressure_b_pa", "pulse_a_s", "pulse_b_s"):
            with self.subTest(key=key):
                result = simulate({key: 0})
                np.testing.assert_allclose(result["spatial"]["values"], 0, atol=1e-12)
                self.assertTrue(any("정의되지" in d["message"] for d in result["diagnostics"]))

    def test_long_separated_pulses_saturate(self):
        first = simulate({"pulse_a_s": 2, "purge_a_s": 3, "purge_b_s": 3})
        second = simulate({"pulse_a_s": 5, "purge_a_s": 3, "purge_b_s": 3})
        self.assertAlmostEqual(metric(first, "gpc_nm"), 0.1, places=6)
        self.assertAlmostEqual(metric(second, "gpc_nm"), metric(first, "gpc_nm"), places=6)

    def test_chamber_purge_matches_first_order_solution(self):
        expected_b = 30 * (1 - math.exp(-0.5 / 0.15)) * math.exp(-1.5 / 0.15)
        pressure = self.baseline["series"][0]
        actual_b = pressure["lines"][1]["values"][-1]
        self.assertAlmostEqual(actual_b, expected_b, delta=1e-7)

    def test_cycles_are_explicit_linear_projection(self):
        first = simulate({"cycles": 1})
        second = simulate({"cycles": 10})
        np.testing.assert_allclose(np.array(first["spatial"]["values"]) * 10,
                                   second["spatial"]["values"], rtol=1e-12)
        self.assertEqual(second["effective"]["cycle_projection"], "first_cycle_times_N")

    def test_starvation_changes_input_and_reduces_growth(self):
        normal = simulate({"pressure_a_pa": 2})
        failed = simulate({"pressure_a_pa": 2}, "precursor_starvation")
        self.assertAlmostEqual(failed["effective"]["pressure_a_pa"], 1.3)
        self.assertLess(metric(failed, "gpc_nm"), metric(normal, "gpc_nm"))
        self.assertLess(failed["spatial"]["values"][-1], normal["spatial"]["values"][-1])

    def test_complete_starvation_is_zero_growth(self):
        result = simulate({"fault_severity": 1}, "precursor_starvation")
        self.assertEqual(metric(result, "gpc_nm"), 0)

    def test_purge_fault_changes_state_and_overlap(self):
        failed = simulate({}, "purge_restriction")
        self.assertGreater(failed["effective"]["pump_tau_s"], self.baseline["effective"]["pump_tau_s"])
        self.assertGreater(metric(failed, "overlap_pa_s"), metric(self.baseline, "overlap_pa_s"))
        self.assertGreater(metric(failed, "residual_pressure_pa"), metric(self.baseline, "residual_pressure_pa"))
        self.assertTrue(any("깨끗한 초기 상태" in d["message"] for d in failed["diagnostics"]))
        recovered = simulate({"purge_a_s": 8, "purge_b_s": 8}, "purge_restriction")
        self.assertLess(metric(recovered, "overlap_pa_s"), metric(failed, "overlap_pa_s"))

    def test_heater_fault_changes_temperature_and_kinetics(self):
        failed = simulate({}, "heater_drift")
        self.assertAlmostEqual(failed["effective"]["temperature_c"], 179)
        self.assertLess(failed["effective"]["sticking_a"], self.baseline["effective"]["sticking_a"])

    def test_zero_severity_matches_baseline_for_all_faults(self):
        for fault in ("precursor_starvation", "purge_restriction", "heater_drift"):
            with self.subTest(fault=fault):
                actual = simulate({"fault_severity": 0}, fault)
                np.testing.assert_allclose(actual["spatial"]["values"], self.baseline["spatial"]["values"], atol=1e-12)

    def test_coverage_bounds(self):
        coverage = next(s for s in self.baseline["series"] if s["key"] == "coverage")
        for line in coverage["lines"]:
            self.assertGreaterEqual(min(line["values"]), -1e-6)
            self.assertLessEqual(max(line["values"]), 1 + 1e-6)

    def test_grid_refinement_reduces_mean_growth_error(self):
        params = _validate({"pressure_a_pa": 5, "depth_um": 80}, "none")
        means = [_solve_cycle(params, "none", cells=n)["growth"][-1].mean() for n in (18, 36, 72)]
        coarse_change = abs(means[1] - means[0])
        fine_change = abs(means[2] - means[1])
        self.assertLess(fine_change, coarse_change / 2)
        self.assertLess(fine_change / means[2], 0.002)

    def test_solver_tolerance_refinement(self):
        params = _validate({}, "none")
        normal = _solve_cycle(params, "none", rtol=2e-7)
        tight = _solve_cycle(params, "none", rtol=2e-8)
        np.testing.assert_allclose(normal["growth"][-1], tight["growth"][-1], rtol=2e-4, atol=1e-7)

    def test_invalid_inputs_rejected(self):
        cases = [{"temperature_c": float("nan")}, {"pulse_a_s": float("inf")},
                 {"pressure_a_pa": -1}, {"cycles": True}, {"cycles": 1.5},
                 {"pressure_a_pa": "20"}, {"unknown": 1},
                 {"pulse_a_s": 0, "pulse_b_s": 0, "purge_a_s": 0, "purge_b_s": 0}]
        for params in cases:
            with self.subTest(params=params), self.assertRaises(ValueError):
                simulate(params)
        with self.assertRaises(ValueError):
            simulate({}, "unknown_fault")

    def test_stiff_short_channel_remains_within_bounds(self):
        result = simulate({"depth_um": 1, "gap_um": 2, "pressure_a_pa": 200,
                           "pressure_b_pa": 200, "sticking_a": 0.01,
                           "sticking_b": 0.01, "temperature_c": 350,
                           "activation_ev": 0.3, "pulse_a_s": 5,
                           "pulse_b_s": 5, "purge_a_s": 8, "purge_b_s": 8})
        json.dumps(result, allow_nan=False)
        self.assertAlmostEqual(metric(result, "gpc_nm"), 0.1, places=5)

    def test_fast_pressure_overlap_is_not_lost_between_plot_samples(self):
        # Equal inlet pressures and time constants: after an unpurged A pulse,
        # integral min(P exp(-t/tau), P(1-exp(-t/tau))) = P*tau*ln(2).
        result = simulate({"pressure_a_pa": 200, "pressure_b_pa": 200,
                           "residence_time_s": 0.02, "pulse_a_s": 5,
                           "pulse_b_s": 5, "purge_a_s": 0, "purge_b_s": 0})
        self.assertAlmostEqual(metric(result, "overlap_pa_s"), 200 * 0.02 * math.log(2), places=6)

    def test_all_defaults_are_valid(self):
        values = {p["key"]: p["default"] for p in PARAMS}
        self.assertEqual(_validate(values, "none"), _validate({}, "none"))


if __name__ == "__main__":
    unittest.main()
