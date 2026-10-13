import copy
import tempfile
import unittest
from pathlib import Path
import json
import numpy as np
from flow_lab.model import IDS, accessible_gas, conformal_deposit, presets, selective_front, simulate, validate
from flow_lab.service import run_request


def recipe(steps, grid=2):
    return dict(domain=dict(width_nm=80, bottom_nm=-20, top_nm=80, grid_nm=grid), steps=steps)


def step(kind, **kwargs):
    return dict(id=kind, name=kind, kind=kind, **kwargs)


def decode(run, frame=-1):
    grid=np.zeros(run['shape'],dtype=np.uint8)
    for row,col,count,material in run['frames'][frame]['spans']:
        grid[row,col:col+count]=material
    return grid


class FlowTests(unittest.TestCase):
    def test_planar_deposition_and_etch_known_area(self):
        r=simulate(recipe([step('deposit', amount_nm=8, material='HfO2'),
                           step('directional_etch', amount_nm=4, material='HfO2')]))
        self.assertEqual(r['frames'][1]['metrics']['area_nm2']['HfO2'],80*8)
        self.assertEqual(r['frames'][2]['metrics']['area_nm2']['HfO2'],80*4)
        self.assertEqual(r['frames'][2]['metrics']['area_nm2']['Si'],80*20)
        self.assertEqual(r['frames'][2]['parent_hash'],r['frames'][1]['state_hash'])

    def test_step_order_and_prefix_are_real_state_continuation(self):
        a=recipe([step('deposit', amount_nm=8, material='HfO2'),step('directional_etch', amount_nm=4, material='HfO2')])
        full=simulate(a);prefix=simulate({**a,'stop_after':1})
        self.assertEqual(prefix['frames'][-1],full['frames'][1])
        b=simulate({**a,'steps':list(reversed(a['steps']))})
        self.assertNotEqual(full['frames'][-1]['state_hash'],b['frames'][-1]['state_hash'])

    def test_mask_protects_columns_and_strip_restores_access(self):
        r=simulate(recipe([step('mask',width_nm=20,center_nm=0),step('directional_etch',amount_nm=4,material='Si')]))
        self.assertEqual(r['frames'][-1]['metrics']['area_nm2']['Si'],80*20-60*4)
        self.assertEqual(len(r['frames'][-1]['mask_columns']),10)
        small=simulate(recipe([step('mask',width_nm=2,center_nm=0)]))
        self.assertEqual(len(small['frames'][-1]['mask_columns']),1)

    def test_buried_material_not_etched_through_protective_layer(self):
        g=np.ones((12,12),dtype=np.uint8);g[-4:]=0;g[4:6,4:8]=IDS['SiGe']
        etched=selective_front(g,IDS['SiGe'],4,100,1)
        self.assertTrue(np.array_equal(g,etched))

    def test_finite_selectivity_causes_more_non_target_loss(self):
        g=np.ones((12,12),dtype=np.uint8);g[-4:]=0;g[5:8,3:9]=IDS['SiGe']
        low=selective_front(g,IDS['SiGe'],4,1,1)
        high=selective_front(g,IDS['SiGe'],4,100,1)
        self.assertLess(np.sum(low==IDS['Si']),np.sum(high==IDS['Si']))

    def test_enclosed_void_not_reachable(self):
        g=np.ones((10,10),dtype=np.uint8);g[-2:]=0;g[4:6,4:6]=0
        self.assertFalse(accessible_gas(g)[4,4])
        self.assertTrue(accessible_gas(g)[-1,4])

    def test_deposition_stops_inside_a_void_sealed_during_the_step(self):
        grid=np.ones((20,20),dtype=np.uint8)
        grid[-3:]=0
        grid[12:17,9:11]=0  # 2-cell access throat
        grid[4:12,5:15]=0   # wider cavity
        coated=conformal_deposit(grid,IDS['HfO2'],6,1)
        self.assertEqual(coated[8,9],0)  # centre remains empty after throat closure
        self.assertFalse(accessible_gas(coated)[8,9])
        self.assertTrue(np.all(coated[grid==IDS['Si']]==IDS['Si']))

    def test_planar_selective_front_depth_and_material_loss_limit(self):
        g=np.ones((20,20),dtype=np.uint8);g[10:]=0
        target=selective_front(g,IDS['Si'],4,100,1)
        non_target=selective_front(g,IDS['SiGe'],4,2,1)
        self.assertEqual(np.sum(g!=0)-np.sum(target!=0),80)
        self.assertEqual(np.sum(g!=0)-np.sum(non_target!=0),40)

    def test_gaa_has_three_separate_si_sheets_and_release_removes_sige(self):
        p=presets()[0];r=simulate({k:v for k,v in p.items() if k!='id'})
        self.assertEqual(r['frames'][5]['metrics']['si_components_above_zero'],3)
        self.assertEqual(r['frames'][5]['metrics']['area_nm2']['SiGe'],0)
        self.assertGreater(r['frames'][-1]['metrics']['area_nm2']['HfO2'],0)
        self.assertGreater(r['frames'][-1]['metrics']['area_nm2']['TiN'],0)
        self.assertEqual(r['frames'],simulate(r['request'])['frames'])

    def test_grid_refinement_planar_limit(self):
        values=[simulate(recipe([step('deposit',amount_nm=8,material='HfO2')],grid=g))['frames'][-1]['metrics']['area_nm2']['HfO2'] for g in (1,2,4)]
        self.assertEqual(values,[640]*3)

    def test_invalid_inputs_rejected_and_zero_process_no_change(self):
        r=simulate(recipe([step('deposit',amount_nm=0,material='HfO2')]))
        self.assertEqual(r['frames'][0]['state_hash'],r['frames'][1]['state_hash'])
        for bad in [recipe([step('deposit',amount_nm=float('nan'),material='Si')]),
                    recipe([step('deposit',amount_nm=True,material='Si')]),
                    recipe([step('deposit',amount_nm=2,material='fake')]),
                    {**recipe([]),'stop_after':1}]:
            with self.assertRaises(ValueError):validate(bad)
        bad=recipe([]);bad['domain']['width_nm']=81
        with self.assertRaises(ValueError):validate(bad)

    def test_incompatible_sequence_fails_instead_of_fabricating_surface(self):
        with self.assertRaisesRegex(ValueError,'마스크'):
            simulate(recipe([step('mask',width_nm=20,center_nm=0),step('deposit',amount_nm=4,material='Si')]))

    def test_result_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            result=run_request(recipe([]),folder)
            self.assertEqual(json.loads((Path(folder)/result['run_id']/'result.json').read_text(encoding='utf-8')),result)


if __name__=='__main__':unittest.main()
