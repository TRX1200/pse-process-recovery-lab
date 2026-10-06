import math
import unittest
from native_lab.engine import simulate
from native_lab.schema import validate


class ProfileTests(unittest.TestCase):
    def test_ripple_initial_rms_and_zero_flux_retention(self):
        result = simulate({'model':'etch','params':{'surface_profile':1,'grid_nm':2,
            'ion_flux':0,'fluorine_flux':0,'oxygen_flux':0,'output_steps':4}})
        first,last = result['frames'][0],result['frames'][-1]
        self.assertEqual(first['layers'],last['layers'])
        self.assertAlmostEqual(first['metrics']['roughness_rq_nm']/(8/math.sqrt(2)),1,delta=.005)
        self.assertEqual(last['metrics']['mean_advance_nm'],0)

    def test_scallop_zero_exposure_retains_walls(self):
        result = simulate({'model':'ald','params':{'surface_profile':2,'grid_nm':2,
            'depth_nm':240,'pulse_s':0,'cycles':5}})
        first,last = result['frames'][0],result['frames'][-1]
        self.assertEqual(first['layers'],last['layers'])
        self.assertGreater(first['metrics']['left_wall_rq_nm'],2)
        self.assertAlmostEqual(first['metrics']['left_wall_rq_nm'],first['metrics']['right_wall_rq_nm'],places=8)

    def test_ald_growth_moves_the_solved_ripple_surface(self):
        result = simulate({'model':'ald','params':{'surface_profile':1,'grid_nm':2,
            'cycles':5,'rays_per_point':100}})
        self.assertGreater(result['frames'][-1]['metrics']['mean_advance_nm'],0)
        self.assertNotEqual(result['frames'][0]['layers'],result['frames'][-1]['layers'])

    def test_under_resolved_corrugation_is_rejected(self):
        for params in [{'surface_profile':1}, {'surface_profile':1,'grid_nm':4,'corrugation_count':12},
                       {'surface_profile':2,'grid_nm':2,'corrugation_amplitude_nm':80,'width_nm':250}]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                validate({'model':'etch','params':params})


if __name__ == '__main__':
    unittest.main()
