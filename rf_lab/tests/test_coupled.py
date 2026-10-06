import math
import unittest

from rf_lab.coupled import simulate, global_terms, equilibrium, validate_gas
from rf_lab.model import validate


class CoupledTests(unittest.TestCase):
    def test_balances_and_circuit_power_are_jointly_satisfied(self):
        result = simulate({'rf_params':{}})
        self.assertLess(result['terms']['particle_relative_residual'],1e-9)
        for key in ['manual','matched']:
            state = result[key]['selected']
            self.assertIsNotNone(state)
            self.assertLess(state['power_relative_residual'],1e-8)
            self.assertLess(abs(state['circuit']['power_residual_w']),1e-8)
            self.assertLess(state['normalized_slope'],0)
        self.assertGreater(result['matched']['selected']['density_m3'],result['manual']['selected']['density_m3'])

    def test_prescribed_density_is_not_used_as_the_coupled_solution(self):
        a = simulate({'rf_params':{}})
        b = simulate({'rf_params':{'density_1e15_m3':100,'collision_1e8_s':10}})
        self.assertEqual(a['manual'],b['manual'])
        self.assertEqual(a['terms'],b['terms'])

    def test_zero_power_and_cable_invariance(self):
        self.assertIsNone(simulate({'rf_params':{'forward_w':0}})['manual']['selected'])
        a = simulate({'rf_params':{'cable_m':0}})['manual']['selected']
        b = simulate({'rf_params':{'cable_m':3}})['manual']['selected']
        self.assertAlmostEqual(a['density_m3']/b['density_m3'],1,places=10)

    def test_root_search_refinement(self):
        rf = validate({})
        terms = global_terms(rf,validate_gas({}))
        a,b = equilibrium(rf,terms,samples=160),equilibrium(rf,terms,samples=640)
        self.assertEqual(len(a['roots']),len(b['roots']))
        self.assertAlmostEqual(a['selected']['density_m3']/b['selected']['density_m3'],1,places=9)

    def test_invalid_and_outside_fit_are_not_fabricated_solutions(self):
        for raw in [{'unknown':1},{'pressure_mtorr':math.nan},{'gas_temperature_k':True}]:
            with self.assertRaises(ValueError): validate_gas(raw)
        with self.assertRaises(ValueError):
            simulate({'rf_params':{'bulk_mm':2},'gas':{'pressure_mtorr':1}})


if __name__ == '__main__':
    unittest.main()
