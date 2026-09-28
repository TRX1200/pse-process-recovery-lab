"""Numerical and physical-invariant tests, not equipment validation."""

import json
import math
import unittest

from sim_app.models.etch import (
    FAULTS, K_B, MTORR_TO_PA, PARAMS, PARTICLES_PER_SCCM_S,
    _coverage_integral, _yield, simulate,
)


def metrics(result):
    return {metric["key"]: metric["value"] for metric in result["metrics"]}


class EtchModelTests(unittest.TestCase):
    def test_default_balances_and_finite_schema(self):
        result = simulate({})
        json.dumps(result, allow_nan=False)
        state = result["effective"]
        self.assertEqual(state["status"], "steady")
        self.assertGreater(state["electron_density_m3"], 0)
        self.assertTrue(1 <= state["electron_temperature_ev"] <= 7)
        self.assertLess(state["particle_balance_relative_residual"], 1e-12)
        self.assertLess(state["power_balance_relative_residual"], 1e-12)
        self.assertLess(state["radical_balance_relative_residual"], 1e-12)
        self.assertTrue(0 <= state["surface_coverage"] <= 1)
        for series in result["series"]:
            for line in series["lines"]:
                self.assertEqual(len(series["x"]), len(line["values"]))
        self.assertEqual(len(result["spatial"]["x"]), len(result["spatial"]["values"]))

    def test_units_and_delivered_power(self):
        state = simulate({"source_power_w": 1000, "reflected_fraction": .2,
                          "coupling_efficiency": .6, "source_duty": .5,
                          "gas_temperature_k": 300, "pressure_mtorr": 10})["effective"]
        self.assertAlmostEqual(state["absorbed_power_w"], 240)
        self.assertAlmostEqual(state["neutral_density_m3"] / (10 * MTORR_TO_PA / (K_B * 300)), 1)
        # 1 sccm at 273.15 K and 1 atm is ~4.48e17 molecules/s.
        self.assertTrue(4.47e17 < PARTICLES_PER_SCCM_S < 4.49e17)

    def test_zero_source_has_no_plasma_even_with_bias(self):
        for off in ({"source_power_w": 0}, {"coupling_efficiency": 0},
                    {"source_duty": 0}, {"reflected_fraction": 1}):
            with self.subTest(off=off):
                result = simulate({**off, "bias_voltage_v": 500})
                state = result["effective"]
                self.assertEqual(state["status"], "off")
                for key in ("electron_density_m3", "electron_temperature_ev", "radical_density_m3",
                            "ion_flux_m2_s", "ion_energy_ev", "etch_rate_nm_min", "etch_depth_nm"):
                    self.assertEqual(state[key], 0)
                self.assertFalse(state["selectivity_defined"])
                json.dumps(result, allow_nan=False)

    def test_pure_argon_power_scaling_at_fixed_pressure(self):
        low = simulate({"source_power_w": 300, "reactive_fraction": 0})["effective"]
        high = simulate({"source_power_w": 600, "reactive_fraction": 0})["effective"]
        self.assertEqual(low["electron_temperature_ev"], high["electron_temperature_ev"])
        self.assertAlmostEqual(high["electron_density_m3"] / low["electron_density_m3"], 2)
        self.assertEqual(low["radical_density_m3"], 0)
        self.assertEqual(high["dissociation_power_w"], 0)

    def test_bias_changes_ion_energy_but_not_source_balance(self):
        low = simulate({"bias_voltage_v": 60})["effective"]
        high = simulate({"bias_voltage_v": 240})["effective"]
        self.assertEqual(low["electron_density_m3"], high["electron_density_m3"])
        self.assertGreater(high["ion_energy_ev"], low["ion_energy_ev"])
        self.assertGreater(high["mask_rate_nm_min"], low["mask_rate_nm_min"])

    def test_faults_modify_upstream_conditions_and_restore(self):
        base = simulate({})
        state = base["effective"]
        rf = simulate({}, "rf_mismatch")["effective"]
        self.assertGreater(rf["reflected_fraction"], state["reflected_fraction"])
        self.assertLess(rf["absorbed_power_w"], state["absorbed_power_w"])
        self.assertLess(rf["electron_density_m3"], state["electron_density_m3"])
        pressure = simulate({}, "pressure_drift")["effective"]
        self.assertAlmostEqual(pressure["actual_pressure_mtorr"], 27)
        gas = simulate({}, "gas_starvation")["effective"]
        self.assertLess(gas["reactive_flow_sccm"], state["reactive_flow_sccm"])
        self.assertLess(gas["radical_density_m3"], state["radical_density_m3"])
        wall = simulate({}, "wall_recombination")["effective"]
        self.assertGreater(wall["wall_recombination"], state["wall_recombination"])
        self.assertLess(wall["radical_density_m3"], state["radical_density_m3"])
        for fault in FAULTS:
            restored = simulate({"fault_severity": 0}, fault["id"])
            self.assertEqual(metrics(restored), metrics(base))
        # Re-running baseline does not retain fault state or modify inputs.
        self.assertEqual(simulate({}), base)

    def test_radical_particle_budget(self):
        for fault in FAULTS:
            state = simulate({}, fault["id"])["effective"]
            supply_limit = 2 * state["reactive_flow_sccm"] * PARTICLES_PER_SCCM_S
            self.assertLessEqual(state["radical_generation_s"], supply_limit)
            self.assertLessEqual(state["wafer_radical_consumption_s"], state["radical_generation_s"])
            self.assertGreaterEqual(state["radical_generation_s"], 0)

    def test_surface_and_time_limiting_cases(self):
        no_time = metrics(simulate({"process_time_s": 0}))
        self.assertEqual(no_time["etch_depth_nm"], 0)
        self.assertEqual(no_time["mask_loss_nm"], 0)
        self.assertGreater(no_time["etch_rate_nm_min"], 0)
        no_remove = simulate({"etch_yield_scale": 0, "sputter_yield_scale": 0,
                              "chemical_rate_s": 0})["effective"]
        self.assertEqual(no_remove["etch_rate_nm_min"], 0)
        self.assertEqual(no_remove["etch_depth_nm"], 0)
        normal = metrics(simulate({"process_time_s": 60}))
        self.assertLessEqual(normal["etch_depth_nm"], normal["etch_rate_nm_min"])
        self.assertGreater(normal["etch_depth_nm"], normal["etch_rate_nm_min"] * .95)
        self.assertEqual(_yield(20, 20, 1), 0)
        self.assertEqual(_yield(5, 20, 1), 0)
        self.assertGreater(_yield(40, 20, 1), 0)
        self.assertAlmostEqual(_coverage_integral(2, 1e-9) / 1e-18, 1, places=8)
        self.assertAlmostEqual(_coverage_integral(2, 100), 99.5)

    def test_uniform_profile_has_zero_nonuniformity(self):
        result = simulate({"radial_nonuniformity": 0})
        values = result["spatial"]["values"]
        self.assertEqual(min(values), max(values))
        self.assertEqual(metrics(result)["nonuniformity_pct"], 0)

    def test_outside_rate_fit_is_marked_unavailable(self):
        result = simulate({"pressure_mtorr": 1, "gas_temperature_k": 800,
                           "radius_mm": 80, "height_mm": 30,
                           "ion_cross_section_1e19_m2": 1, "reactive_fraction": .2})
        self.assertEqual(result["effective"]["status"], "outside_rate_fit")
        self.assertEqual(result["effective"]["electron_density_m3"], 0)
        self.assertTrue(any(d["level"] == "warning" for d in result["diagnostics"]))
        json.dumps(result, allow_nan=False)

    def test_invalid_input_is_rejected(self):
        bad = [{"not_a_parameter": 1}, {"source_power_w": True}, {"source_power_w": "600"},
               {"source_power_w": math.nan}, {"source_power_w": math.inf},
               {"source_power_w": -1}, {"reactive_fraction": .21},
               {"pressure_mtorr": None}, {"radius_mm": 0}, None, []]
        for params in bad:
            with self.subTest(params=params), self.assertRaises(ValueError):
                simulate(params)
        for fault in ("unknown", False, None, []):
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                simulate({}, fault)

    def test_all_exposed_parameter_boundaries_are_finite(self):
        for param in PARAMS:
            for value in (param["min"], param["max"]):
                with self.subTest(parameter=param["key"], value=value):
                    result = simulate({param["key"]: value})
                    json.dumps(result, allow_nan=False)
                    for metric in result["metrics"]:
                        self.assertGreaterEqual(metric["value"], 0)


if __name__ == "__main__":
    unittest.main()
