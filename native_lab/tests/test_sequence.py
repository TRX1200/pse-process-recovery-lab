"""Native process handoff and response tests, not physical calibration."""
import tempfile
import time
import unittest
from pathlib import Path

from native_lab.sequence import simulate
from native_lab.schema import validate
from native_lab.jobs import JobManager

SMALL = {'duration_s': .4, 'output_steps': 4, 'rays_per_point': 100, 'cycles': 20}


class SequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = simulate({'model': 'sequence', 'params': SMALL})

    def test_geometry_handoff_and_immobile_si_during_ald(self):
        run = self.baseline
        self.assertEqual([l['material'] for l in run['etch']['frames'][-1]['layers']], ['Mask', 'Si'])
        self.assertEqual([l['material'] for l in run['strip']['layers']], ['Si'])
        self.assertTrue(run['handoff']['si_contour_preserved'])
        substrate = run['strip']['layers'][0]
        for frame in run['ald']['frames']:
            self.assertEqual(frame['layers'][0], substrate)
        self.assertGreater(run['handoff']['derived_depth_nm'], 0)
        for key in ('top_film_nm', 'bottom_film_nm'):
            self.assertEqual(run['ald']['frames'][0]['metrics'][key], 0)
            self.assertGreater(run['ald']['frames'][-1]['metrics'][key], 0)

    def test_seed_reproducibility_and_exposure_response(self):
        again = simulate({'model': 'sequence', 'params': SMALL})
        self.assertEqual(again['ald']['frames'], self.baseline['ald']['frames'])
        self.assertEqual(again['run_hash'], self.baseline['run_hash'])
        short = simulate({'model': 'sequence', 'params': {**SMALL, 'pulse_s': .0005}})
        self.assertEqual(short['handoff'], again['handoff'])
        self.assertLess(short['ald']['frames'][-1]['metrics']['top_film_nm'],
                        again['ald']['frames'][-1]['metrics']['top_film_nm'])

    def test_no_etch_no_exposure_and_mask_strip(self):
        run = simulate({'model': 'sequence', 'params': {**SMALL, 'duration_s': 0, 'pulse_s': 0}})
        self.assertEqual(run['etch']['frames'][0]['layers'], run['etch']['frames'][-1]['layers'])
        self.assertEqual(run['ald']['frames'][0]['layers'], run['ald']['frames'][-1]['layers'])
        self.assertIsNone(run['ald']['frames'][-1]['metrics']['mid_gap_nm'])
        self.assertNotEqual(run['handoff']['geometry_sha256'], self.baseline['handoff']['geometry_sha256'])
        # After Boolean mask removal, protected Si is near y=0, not mask top.
        ys = [y for path in run['strip']['layers'][0]['paths_nm'] for _, y in path]
        self.assertLess(max(abs(y) for y in ys), SMALL.get('grid_nm', 5))

    def test_invalid_inputs_rejected_before_native_work(self):
        for bad in ({'duration_s': float('nan')}, {'cycles': True}, {'surface_profile': 1},
                    {'depth_nm': 400}, {'width_nm': 300, 'pitch_nm': 200}):
            with self.assertRaises(ValueError):
                validate({'model': 'sequence', 'params': bad})

    def test_subprocess_persistence_and_stage_files(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = JobManager(temp)
            try:
                job = manager.submit({'model': 'sequence', 'params': {**SMALL, 'duration_s': 0, 'pulse_s': 0}})
                deadline = time.monotonic()+20
                while time.monotonic() < deadline:
                    status = manager.status(job['id'])
                    if status['state'] not in ('queued', 'running'):
                        break
                    time.sleep(.05)
                self.assertEqual(status['state'], 'complete', status)
                run = manager.result(job['id'])
                self.assertEqual(run['format'], 'native-sequence-run-v1')
                root = Path(temp)/job['id']
                self.assertTrue(list((root/'01_etch').glob('final_surface*')))
                self.assertTrue(list((root/'03_ald').glob('final_levelset*')))
                self.assertTrue((root/'02_strip.json').exists())
            finally:
                manager.close()


if __name__ == '__main__':
    unittest.main()
