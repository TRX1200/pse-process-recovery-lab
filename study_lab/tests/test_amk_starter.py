import math
import sys
import unittest
from pathlib import Path
from statistics import mean

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_amk_starter import generate_pvd


class PvdFixtureTests(unittest.TestCase):
    def test_determinism_and_seed_effect(self):
        self.assertEqual(generate_pvd(17),generate_pvd(17))
        self.assertNotEqual(generate_pvd(17),generate_pvd(18))

    def test_truth_is_separate_and_all_sites_match_a_wafer(self):
        data=generate_pvd(17)
        ids={r['wafer_id'] for r in data['truth']}
        self.assertEqual(ids,{r['wafer_id'] for r in data['sites']})
        self.assertEqual(len(data['sites']),45*9)
        for r in data['sites']:
            self.assertNotIn('injected_state',r)
            self.assertNotIn('latent_resistivity_ohm_m',r)
        keys=[(r['wafer_id'],r['site_id']) for r in data['sites']]
        self.assertEqual(len(keys),len(set(keys)))

    def test_resistivity_change_with_nearly_unchanged_thickness(self):
        rows=generate_pvd(17)['wafers']
        base=[r for r in rows if r['case_id']=='BASELINE']
        fault=[r for r in rows if r['case_id']=='CASE_A']
        self.assertLess(abs(mean(r['mean_thickness_reference_nm'] for r in base)-mean(r['mean_thickness_reference_nm'] for r in fault)),.1)
        ratio=mean(r['mean_sheet_resistance_ohm_sq'] for r in fault)/mean(r['mean_sheet_resistance_ohm_sq'] for r in base)
        self.assertTrue(1.23<ratio<1.27)

    def test_monitor_bias_does_not_change_reference_or_resistance(self):
        rows=generate_pvd(17)['wafers']
        base=[r for r in rows if r['case_id']=='BASELINE']
        fault=[r for r in rows if r['case_id']=='CASE_B']
        delta=mean(r['mean_thickness_monitor_nm']-r['mean_thickness_reference_nm'] for r in fault)
        self.assertTrue(1.95<delta<2.05)
        self.assertLess(abs(mean(r['mean_sheet_resistance_ohm_sq'] for r in fault)-mean(r['mean_sheet_resistance_ohm_sq'] for r in base)),.1)

    def test_resistance_thickness_product_recovers_assumed_rho(self):
        data=generate_pvd(17)
        refs={r['wafer_id']:r['latent_resistivity_ohm_m'] for r in data['truth']}
        for row in data['sites']:
            rho_est=row['sheet_resistance_ohm_sq']*row['thickness_reference_nm']*1e-9
            self.assertLess(abs(rho_est/refs[row['wafer_id']]-1),.025)

    def test_summary_uniformity_uses_stated_definition(self):
        data=generate_pvd(17)
        for wafer in data['wafers']:
            values=[r['thickness_monitor_nm'] for r in data['sites'] if r['wafer_id']==wafer['wafer_id']]
            nu=100*(max(values)-min(values))/(2*mean(values))
            self.assertAlmostEqual(wafer['nu_range_pct'],nu,places=4)
        for row in data['sites']:
            self.assertLessEqual(math.hypot(row['x_mm'],row['y_mm']),145)
            for key,value in row.items():
                if isinstance(value,(float,int)):
                    self.assertTrue(math.isfinite(value))

    def test_invalid_seed(self):
        for seed in (-1,1.2,True,'17'):
            with self.assertRaises(ValueError):
                generate_pvd(seed)


if __name__=='__main__':
    unittest.main()
