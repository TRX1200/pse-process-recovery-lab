import cmath
import math
import tempfile
import unittest
from pathlib import Path
import numpy as np
from rf_lab.model import validate, point, load_elements, tune, simulate, Z0
from rf_lab.service import connect, persist


class RFTests(unittest.TestCase):
    def test_public_validation(self):
        for raw in [[], {'unknown':1}, {'cp_pf':0}, {'cp_pf':True}, {'coil_q':float('nan')}, {'forward_w':float('inf')}]:
            with self.assertRaises(ValueError): validate(raw)

    def test_independent_nodal_solution(self):
        # Independent 3-node admittance matrix, matched Thevenin source, no line.
        p=validate({'cable_m':0})
        r=point(p)
        w=2*math.pi*p['frequency_mhz']*1e6
        rb,lb,csh=load_elements(p)
        zcoil=w*p['coil_uh']*1e-6*(1/p['coil_q']+1j)
        zcs=(1/p['capacitor_q']-1j)/(w*p['cs_pf']*1e-12)
        zcp=(1/p['capacitor_q']-1j)/(w*p['cp_pf']*1e-12)
        zpl=rb+1j*w*lb+1/(1j*w*csh)
        y=np.array([[1/Z0+1/zcp+1/zcoil,-1/zcoil,0],
                    [-1/zcoil,1/zcoil+1/zcs,-1/zcs],
                    [0,-1/zcs,1/zcs+1/zpl]],dtype=complex)
        drive=2*math.sqrt(p['forward_w']*Z0)
        v=np.linalg.solve(y,[drive/Z0,0,0])
        independent_bulk=abs(v[2]/zpl)**2*rb
        self.assertAlmostEqual(r['bulk_w'],independent_bulk,places=9)
        self.assertAlmostEqual(complex(*r['load_voltage']).real,v[2].real,places=9)
        self.assertAlmostEqual(complex(*r['load_voltage']).imag,v[2].imag,places=9)

    def test_passivity_power_balance_over_seeded_inputs(self):
        rng=np.random.default_rng(42)
        for _ in range(120):
            p=validate({'cp_pf':float(rng.uniform(10,3000)), 'cs_pf':float(rng.uniform(10,3000)),
                        'frequency_mhz':float(rng.uniform(5,40)), 'coil_q':float(rng.uniform(5,200)),
                        'density_1e15_m3':float(rng.uniform(.1,100)), 'cable_m':float(rng.uniform(0,5))})
            r=point(p)
            self.assertGreater(r['z_generator'][0],0)
            self.assertLessEqual(r['reflected_pct'],100+1e-10)
            self.assertLess(abs(r['power_residual_w']),1e-8)
            self.assertGreaterEqual(r['bulk_w'],0)

    def test_lossless_line_rotates_phase_only(self):
        a=validate({'cable_m':0})
        b={**a,'cable_m':2}
        pa,pb=point(a),point(b)
        theta=2*math.pi*a['frequency_mhz']*1e6*2/(299792458*a['velocity_factor'])
        self.assertLess(abs(complex(*pb['gamma'])-complex(*pa['gamma'])*cmath.exp(-2j*theta)),1e-12)
        self.assertAlmostEqual(pa['bulk_w'],pb['bulk_w'],places=9)
        self.assertAlmostEqual(pa['reflected_pct'],pb['reflected_pct'],places=9)

    def test_zero_power_and_fixed_load_scaling(self):
        p=validate({})
        zero=point({**p,'forward_w':0})
        self.assertEqual(zero['bulk_w'],0)
        self.assertIsNone(zero['bulk_efficiency_pct'])
        a,b=point(p),point({**p,'forward_w':1200})
        self.assertAlmostEqual(b['bulk_w'],4*a['bulk_w'],places=9)
        self.assertAlmostEqual(b['series_cap_rms_v'],2*a['series_cap_rms_v'],places=9)

    def test_density_and_sheath_scaling(self):
        p=validate({})
        r,l,c=load_elements(p)
        rr,ll,cc=load_elements({**p,'density_1e15_m3':2,'sheath_total_mm':2})
        self.assertAlmostEqual(rr,r/2)
        self.assertAlmostEqual(ll,l/2)
        self.assertAlmostEqual(cc,c/2)

    def test_tuner_and_load_change_are_distinct(self):
        r=simulate({})
        self.assertLess(r['matched']['reflected_pct'],1e-6)
        self.assertGreater(r['comparison'][1]['reflected_pct'],1)
        self.assertLess(r['comparison'][2]['reflected_pct'],1e-6)
        self.assertEqual(r['comparison'][1]['cp_pf'],r['matched']['cp_pf'])

    def test_near_lossless_components_and_finite_q_loss(self):
        low=tune(validate({'coil_q':15}))
        high=tune(validate({'coil_q':10000,'capacitor_q':100000}))
        self.assertLess(low['reflected_pct'],1e-6)
        self.assertLess(high['reflected_pct'],1e-6)
        self.assertGreater(high['bulk_w'],.99*300)
        self.assertLess(low['bulk_w'],high['bulk_w'])

    def test_analytical_database_reconciles_latest_run(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.sqlite'
            a=persist(simulate({}),path)
            b=persist(simulate({'forward_w':500}),path)
            with connect(path) as con:
                self.assertEqual(con.execute('SELECT count(*) FROM rf_cases').fetchone()[0],8)
                self.assertEqual(con.execute('SELECT DISTINCT coil_q FROM rf_case_history').fetchall(),[(100.0,)])
                self.assertEqual(con.execute('SELECT DISTINCT run_id FROM rf_latest_cases').fetchall(),[(b['run_id'],)])
                self.assertAlmostEqual(con.execute('SELECT bulk_w FROM rf_cases WHERE run_id=? AND case_name=?',(a['run_id'],'01 기준 정합')).fetchone()[0],a['matched']['bulk_w'])
            con.close()


if __name__=='__main__': unittest.main()
