"""Run the predeclared PECVD comparison using the unchanged module snapshot.

Python 3.12 + requirements.txt. Replays: python run_experiment.py --out NEW_DIR
Existing numerical outputs are never overwritten. No optimization is performed.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import platform
import sys
import uuid

BUNDLE = Path(__file__).resolve().parent
sys.path.insert(0, str(BUNDLE / 'source_snapshot'))
import numpy as np
from studio_lab.engine import simulate, heights_at

def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BUNDLE)
    out = parser.parse_args().out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = out / 'data'
    data.mkdir(exist_ok=False)
    plan = json.loads((BUNDLE / 'plan.json').read_text(encoding='utf-8'))
    for rel, expected in plan['source_sha256'].items():
        assert sha(BUNDLE / 'source_snapshot' / rel) == expected, rel
    versions = {name: importlib.metadata.version(name) for name in plan['versions']}
    assert versions == plan['versions'], versions
    experiment = dict(execution_id=uuid.uuid4().hex, id_kind='Generated experiment ID; direct engine call, not server job ID',
        started_at_utc=now(), scheduled_at_kst=plan['scheduled_at_kst'],
        plan_sha256=sha(BUNDLE / 'plan.json'), historical_results_reused=False,
        versions={**versions, 'python': platform.python_version(), 'platform': platform.platform()}, runs={})
    dump(out / 'execution.json', experiment)
    runs = {}
    try:
        for case in ['A','B','A_replay','zero_rates']:
            native = out / 'native_outputs' / case
            native.mkdir(parents=True, exist_ok=False)
            started = now()
            result = simulate(plan['requests'][case], native)
            runs[case] = result
            payload = json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
            (data / f'{case}.json.gz').write_bytes(gzip.compress(payload, mtime=0))
            experiment['runs'][case] = dict(started_at_utc=started, finished_at_utc=now(),
                run_hash=result['run_hash'], elapsed_s=result['elapsed_s'], frames=len(result['frames']),
                raw_sha256=sha(data / f'{case}.json.gz'))
            dump(out / 'execution.json', experiment)
            print(case, result['frames'][-1]['metrics'], flush=True)
    except Exception as exc:
        experiment.update(state='FAILED', finished_at_utc=now(), error=f'{type(exc).__name__}: {exc}')
        dump(out / 'execution.json', experiment)
        raise

    checks = {}
    def check(name, condition):
        checks[name] = 'PASS' if condition else 'FAIL'
        return bool(condition)
    p_a, p_b = runs['A']['request'], runs['B']['request']
    changed = [k for k in p_a['params'] if p_a['params'][k] != p_b['params'][k]]
    check('only_radical_rate_changed', changed == ['radical_rate_nm_s'] and
          all(p_a[k] == p_b[k] for k in p_a if k != 'params'))
    check('exact_frame_replay', runs['A']['frames'] == runs['A_replay']['frames'])
    check('identical_initial_geometry', runs['A']['frames'][0] == runs['B']['frames'][0])
    check('zero_rates_stationary', runs['zero_rates']['frames'][1]['layers'] == runs['zero_rates']['frames'][-1]['layers'])
    check('known_plane_probe', heights_at([[0,0,2],[2,0,4],[0,2,6]], [[0,1,2]],[(.5,.5),(3,3)]) == [3.5,None])
    finite, indices, timebase, substrate = True, True, True, True
    series, summary, sections = [], {}, []
    for case, run in runs.items():
        initial = run['frames'][0]
        timebase &= [f['at'] for f in run['frames'] if f['stage']=='pecvd'] == [5,10,15,20]
        for frame in run['frames']:
            substrate &= frame['layers'][0] == initial['layers'][0]
            for layer in frame['layers']:
                n = np.asarray(layer['positions_nm']).reshape(-1,3)
                t = np.asarray(layer['triangles']).reshape(-1,3)
                finite &= bool(np.isfinite(n).all())
                indices &= bool(t.min() >= 0 and t.max() < len(n))
            metrics = frame['metrics']
            finite &= all(v is not None and np.isfinite(v) for v in metrics.values())
            finite &= all(z is not None and np.isfinite(z) for z in frame['section']['z_nm'])
            record = dict(case=case, time_s=frame['at'], stage=frame['stage'], **metrics,
                center_delta_z_nm=metrics['center_z_nm']-initial['metrics']['center_z_nm'],
                top_delta_z_nm=metrics['top_z_nm']-initial['metrics']['top_z_nm'],
                remaining_center_recess_nm=metrics['top_z_nm']-metrics['center_z_nm'])
            series.append(record)
        summary[case] = series[-1]
        for x,z0,z1 in zip(initial['section']['x_nm'], initial['section']['z_nm'], run['frames'][-1]['section']['z_nm']):
            sections.append(dict(case=case, x_nm=x, y_nm=0, initial_z_nm=z0, final_z_nm=z1, delta_z_nm=z1-z0))
    check('finite_arrays_and_probes', finite)
    check('triangle_indices_in_bounds', indices)
    check('output_timebase', timebase)
    check('original_substrate_mesh_preserved', substrate)
    check('snapshot_hashes_unchanged', all(sha(BUNDLE/'source_snapshot'/rel)==expected for rel,expected in plan['source_sha256'].items()))
    checks.update(physical_calibration='NOT_RUN', mesh_convergence='NOT_RUN', seed_ensemble='NOT_RUN',
                  chamber_chemistry_validation='NOT_RUN', electrical_device_validation='NOT_RUN')
    def csv_file(name, rows):
        with (data/name).open('w', newline='', encoding='utf-8') as file:
            writer=csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    csv_file('time_series.csv', series)
    csv_file('sections.csv', sections)
    csv_file('summary.csv', list(summary.values()))
    dump(data/'summary.json', summary)
    dump(data/'validation.json', checks)
    experiment.update(state='COMPLETE' if 'FAIL' not in checks.values() else 'VALIDATION_FAILED', finished_at_utc=now())
    dump(out/'execution.json', experiment)
    print(json.dumps(dict(execution=experiment, validation=checks), indent=2), flush=True)
    if experiment['state'] != 'COMPLETE': raise SystemExit(1)

if __name__ == '__main__': main()
