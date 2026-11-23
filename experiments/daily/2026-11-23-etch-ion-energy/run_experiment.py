"""Execute the predeclared Etch comparison with the unchanged module snapshot.

Python 3.12 + requirements.txt. Replay: python run_experiment.py --out NEW_DIR
Existing numerical results are never overwritten. No parameter optimization.
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

def probes(frame, coordinates):
    layer = frame['layers'][-1]
    return heights_at(np.asarray(layer['positions_nm']).reshape(-1,3),
                      np.asarray(layer['triangles']).reshape(-1,3), coordinates)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BUNDLE)
    out = parser.parse_args().out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = out / 'data'
    data.mkdir(exist_ok=False)
    plan = json.loads((BUNDLE/'plan.json').read_text(encoding='utf-8'))
    for rel, expected in plan['source_sha256'].items():
        assert sha(BUNDLE/'source_snapshot'/rel) == expected, rel
    versions = {name:importlib.metadata.version(name) for name in plan['versions']}
    assert versions == plan['versions'], versions
    execution = dict(execution_id=uuid.uuid4().hex,
        id_kind='Generated experiment ID; direct engine call, not server job ID',
        started_at_utc=now(), scheduled_at_kst=plan['scheduled_at_kst'],
        plan_sha256=sha(BUNDLE/'plan.json'), historical_results_reused=False,
        versions={**versions,'python':platform.python_version(),'platform':platform.platform()},runs={})
    dump(out/'execution.json',execution)
    runs = {}
    try:
        for case in ['A','B','A_replay','zero_time']:
            native = out/'native_outputs'/case
            native.mkdir(parents=True,exist_ok=False)
            started = now()
            result = simulate(plan['requests'][case], native)
            runs[case] = result
            payload = json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            (data/f'{case}.json.gz').write_bytes(gzip.compress(payload,mtime=0))
            execution['runs'][case] = dict(started_at_utc=started,finished_at_utc=now(),
                run_hash=result['run_hash'],elapsed_s=result['elapsed_s'],frames=len(result['frames']),
                raw_sha256=sha(data/f'{case}.json.gz'))
            dump(out/'execution.json',execution)
            print(case,result['frames'][-1]['metrics'],flush=True)
    except Exception as exc:
        execution.update(state='FAILED',finished_at_utc=now(),error=f'{type(exc).__name__}: {exc}')
        dump(out/'execution.json',execution)
        raise

    checks = {}
    def check(name, condition): checks[name] = 'PASS' if condition else 'FAIL'
    a,b = runs['A']['request'],runs['B']['request']
    changed = [k for k in a['params'] if a['params'][k]!=b['params'][k]]
    check('only_ion_energy_changed',changed==['energy_ev'] and all(a[k]==b[k] for k in a if k!='params'))
    check('exact_frame_replay',runs['A']['frames']==runs['A_replay']['frames'])
    check('identical_initial_geometry',runs['A']['frames'][0]==runs['B']['frames'][0])
    zero = runs['zero_time']['frames']
    check('zero_time_stationary',all(f['layers']==zero[0]['layers'] for f in zero))
    check('known_plane_probe',heights_at([[0,0,2],[2,0,4],[0,2,6]],[[0,1,2]],[(.5,.5),(3,3)])==[3.5,None])
    coordinates = [plan['probes_xy_nm'][name] for name in ['center','near_edge']]
    finite,indices,timebase,flux_units = True,True,True,True
    series,summary,sections = [],{},[]
    for case,run in runs.items():
        initial = run['frames'][0]
        z0 = np.asarray(probes(initial,coordinates),dtype=float)
        duration = run['request']['params']['etch_s']
        expected = [0]+[duration*(i+1)/4 for i in range(4)]
        timebase &= [f['at'] for f in run['frames']]==expected
        flux_units &= run['plasma']['ion_flux_m2_s']==run['request']['params']['ion_flux']*1e19
        for frame in run['frames']:
            for layer in frame['layers']:
                nodes=np.asarray(layer['positions_nm']).reshape(-1,3)
                triangles=np.asarray(layer['triangles']).reshape(-1,3)
                finite &= bool(np.isfinite(nodes).all())
                indices &= bool(triangles.min()>=0 and triangles.max()<len(nodes))
            z = np.asarray(probes(frame,coordinates),dtype=float)
            finite &= bool(np.isfinite(z).all())
            finite &= all(v is not None and np.isfinite(v) for v in frame['metrics'].values())
            finite &= all(v is not None and np.isfinite(v) for v in frame['section']['z_nm'])
            recession = z0-z
            record=dict(case=case,time_s=frame['at'],stage=frame['stage'],
                center_z_nm=float(z[0]),near_edge_z_nm=float(z[1]),
                center_recession_nm=float(recession[0]),near_edge_recession_nm=float(recession[1]),
                edge_minus_center_recession_nm=float(recession[1]-recession[0]),
                outer_surface_nodes=frame['metrics']['nodes'],outer_surface_triangles=frame['metrics']['triangles'])
            series.append(record)
        summary[case]=series[-1]
        for x,first,last in zip(initial['section']['x_nm'],initial['section']['z_nm'],run['frames'][-1]['section']['z_nm']):
            sections.append(dict(case=case,x_nm=x,y_nm=0,initial_z_nm=first,final_z_nm=last,recession_nm=first-last))
    check('finite_arrays_sections_and_probes',finite)
    check('triangle_indices_in_bounds',indices)
    check('output_timebase',timebase)
    check('incident_flux_unit_conversion',flux_units)
    check('snapshot_hashes_unchanged',all(sha(BUNDLE/'source_snapshot'/rel)==v for rel,v in plan['source_sha256'].items()))
    checks.update(physical_calibration='NOT_RUN',mesh_convergence='NOT_RUN',seed_ensemble='NOT_RUN',
        chamber_chemistry_validation='NOT_RUN',coverage_solver_residual_history='NOT_EXPORTED',
        electrical_device_validation='NOT_RUN')
    for name,rows in [('time_series.csv',series),('sections.csv',sections),('summary.csv',list(summary.values()))]:
        with (data/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    dump(data/'summary.json',summary)
    dump(data/'validation.json',checks)
    execution.update(state='COMPLETE' if 'FAIL' not in checks.values() else 'VALIDATION_FAILED',finished_at_utc=now())
    dump(out/'execution.json',execution)
    print(json.dumps(dict(summary=summary,validation=checks,state=execution['state']),indent=2),flush=True)
    if execution['state']!='COMPLETE': raise SystemExit(1)

if __name__=='__main__': main()
