"""Execute the frozen TSV plan; export raw process frames and grid metrology.

Replay using Python 3.12 + requirements.txt: python run_experiment.py --out NEW_DIR
"""
from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy
import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import platform
import sys
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source_snapshot'))
import numpy as np
from fab_lab.engine import simulate
from fab_lab.electrical import copper_path
from fab_lab.schema import MATERIALS

def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def decode(frame,shape):
    encoded=np.asarray(frame['grid'],dtype=np.int64)
    assert len(encoded)%2==0 and np.all(encoded[1::2]>0)
    assert encoded[1::2].sum()==np.prod(shape)
    flat=np.repeat(encoded[::2],encoded[1::2])
    assert np.isin(flat,[m['id'] for m in MATERIALS]).all()
    return flat.astype(np.uint8).reshape(shape,order='C')
def csv_file(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=HERE)
    out=parser.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=out/'data';data.mkdir(exist_ok=False)
    plan=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    for rel,expected in plan['source_sha256'].items(): assert sha(HERE/'source_snapshot'/rel)==expected
    versions={name:importlib.metadata.version(name) for name in plan['versions']}
    assert versions==plan['versions']
    cases=plan['cases'];bond=plan['bond_step_index']
    restored=deepcopy(cases['B']);restored['steps'][bond]['params']['offset_x']=cases['A']['steps'][bond]['params']['offset_x']
    assert restored==cases['A']
    execution=dict(execution_id=uuid.uuid4().hex,server_job_id=None,
        id_kind='Generated experiment ID; direct engine calls, not a server job ID',
        started_at_utc=now(),scheduled_at_kst=plan['scheduled_at_kst'],plan_sha256=sha(HERE/'plan.json'),
        versions={**versions,'python':platform.python_version()},historical_results_reused=False,runs={},state='RUNNING')
    dump(out/'execution.json',execution)
    checks={}
    def check(name,condition):
        checks[name]='PASS' if bool(condition) else 'FAIL'
        if not condition: raise AssertionError(name)
    try:
        check('single_parameter_change',restored==cases['A'])
        runs={}
        for case,request in cases.items():
            directory=data/case;directory.mkdir()
            started=now();runs[case]=simulate(request,directory=directory)
            payload=json.dumps(runs[case],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            (data/f'{case}.json.gz').write_bytes(gzip.compress(payload,mtime=0))
            execution['runs'][case]=dict(started_at_utc=started,finished_at_utc=now(),run_hash=runs[case]['run_hash'],
                frames=len(runs[case]['frames']),raw_sha256=sha(data/f'{case}.json.gz'))
            replay_start=now();replay=simulate(request)
            check(f'{case}_exact_replay',replay==runs[case])
            execution['runs'][case]['replay']=dict(started_at_utc=replay_start,finished_at_utc=now(),exact_full_result_match=True)
            dump(out/'execution.json',execution)
        check('identical_prebond_frames',runs['A']['frames'][:bond+1]==runs['B']['frames'][:bond+1])
        d=cases['A']['domain'];dx=d['dx'];shape=tuple(d[k] for k in ['nx','ny','nz'])
        before=decode(runs['A']['frames'][bond],shape)
        height=int(np.argwhere(before!=0)[:,2].max())+1
        gap=int(np.floor(cases['A']['steps'][bond]['params']['gap']/dx+.5));shift=height+gap
        lower=before[:,:,height-1]==7
        rho=cases['A']['steps'][-1]['params']['rho']
        summary={};history=[];areas=[];interfaces={};finals={}
        for case,run in runs.items():
            for frame in run['frames']:
                grid=decode(frame,shape)
                check(f'{case}_frame_{frame["index"]}_volume',all(frame['volume_nm3'][m['name']]==int((grid==m['id']).sum())*dx**3 for m in MATERIALS[1:]))
                check(f'{case}_frame_{frame["index"]}_solid_count',frame['solid_cells']==int(np.count_nonzero(grid)))
                history.append(dict(case=case,stage_index=frame['index'],operation=frame['op'],label=frame['label'],
                    cu_volume_nm3=frame['volume_nm3']['Cu'],si_volume_nm3=frame['volume_nm3']['Si'],
                    oxide_volume_nm3=frame['volume_nm3']['SiO2'],solid_cells=frame['solid_cells']))
            final=decode(run['frames'][-1],shape);finals[case]=final
            with np.load(data/case/'final_state.npz',allow_pickle=False) as saved:
                check(case+'_saved_npz_matches_frames',np.array_equal(saved['material'],final))
                check(case+'_finite_npz',all(np.isfinite(saved[k]).all() for k in saved.files))
            p=run['request']['steps'][bond]['params']
            ix=int(round(p['offset_x']/dx));iy=int(round(p['offset_y']/dx))
            xs=slice(max(0,ix),min(shape[0],shape[0]+ix));sx=slice(max(0,-ix),min(shape[0],shape[0]-ix))
            ys=slice(max(0,iy),min(shape[1],shape[1]+iy));sy=slice(max(0,-iy),min(shape[1],shape[1]-iy))
            upper_expected=np.zeros_like(before[:,:,:height])
            upper_expected[xs,ys,:]=before[sx,sy,:height]
            check(case+'_upper_die_translation',np.array_equal(final[:,:,shift:shift+height],upper_expected))
            check(case+'_lower_die_preserved',np.array_equal(final[:,:,:height],before[:,:,:height]))
            check(case+'_bond_Cu_footprint',np.array_equal(final[:,:,shift-1]==7,lower))
            upper=final[:,:,shift]==7
            overlap=lower&upper
            check(case+'_actual_face_overlap',np.array_equal(overlap,(final[:,:,shift-1]==7)&(final[:,:,shift]==7)))
            clipped={m['name']:int((before[:,:,:height]==m['id']).sum()-(upper_expected==m['id']).sum()) for m in MATERIALS[1:]}
            check(case+'_no_Cu_clipping',clipped['Cu']==0)
            check(case+'_Cu_volume_accounting',int((final==7).sum())==2*int((before==7).sum())+int(lower.sum())*gap)
            path=run['frames'][-1]['test']['copper']
            check(case+'_saved_copper_test',path==copper_path(final,dx,rho))
            check(case+'_no_compact_device_result',run['frames'][-1]['test']['compact'] is None)
            summary[case]=dict(offset_x_nm=p['offset_x'],realized_offset_x_nm=ix*dx,bond_interface_z_nm=shift*dx,
                lower_Cu_pad_nm2=int(lower.sum())*dx**2,upper_Cu_pad_nm2=int(upper.sum())*dx**2,
                bond_overlap_nm2=int(overlap.sum())*dx**2,overlap_of_lower_pad_pct=100*int(overlap.sum())/int(lower.sum()),
                connected=path['connected'],resistance_ohm=path.get('resistance_ohm'),min_area_nm2=path.get('min_area_nm2'),
                path_length_nm=path.get('length_nm'),cu_volume_nm3=int((final==7).sum())*dx**3,
                clipped_upper_cells=clipped,bond_warnings=run['frames'][bond+1]['warnings'])
            interfaces[case+'_lower']=lower;interfaces[case+'_upper']=upper;interfaces[case+'_overlap']=overlap
            for k in range(shift+height):
                areas.append(dict(case=case,z_center_nm=(k+.5)*dx,cu_area_nm2=int((final[:,:,k]==7).sum())*dx**2))
        check('lower_die_and_gap_identical',np.array_equal(finals['A'][:,:,:shift],finals['B'][:,:,:shift]))
        # Known uniform conductor and an explicitly severed path, separate from A/B.
        prism=np.ones((8,8,12),dtype=np.uint8);prism[2:6,2:6,:]=7
        known=copper_path(prism,1000,2e-8);analytic=2e-8*12e-6/(16e-12)
        check('known_prism_resistance',known['connected'] and np.isclose(known['resistance_ohm'],analytic,rtol=1e-12,atol=0))
        prism[:,:,6]=1;opened=copper_path(prism,1000,2e-8)
        check('known_open_is_null',not opened['connected'] and opened['resistance_ohm'] is None)
        check('snapshot_hashes_unchanged',all(sha(HERE/'source_snapshot'/rel)==v for rel,v in plan['source_sha256'].items()))
        checks.update(physical_calibration='NOT_RUN',grid_convergence='NOT_RUN',contact_spreading_resistance='NOT_MODELED',
                      stress_thermal_reliability='NOT_MODELED',extracted_si_pi='NOT_MODELED')
        x=(np.arange(shape[0])+.5-shape[0]/2)*dx;y=(np.arange(shape[1])+.5-shape[1]/2)*dx;z=(np.arange(shape[2])+.5)*dx
        iy=shape[1]//2
        np.savez_compressed(data/'sections.npz',A_xz=finals['A'][:,iy,:],B_xz=finals['B'][:,iy,:],
                            **interfaces,x_nm=x,y_nm=y,z_nm=z)
        dump(data/'summary.json',summary)
        csv_file(data/'summary.csv',[{k:v for k,v in dict(case=case,**row).items() if not isinstance(v,(dict,list))} for case,row in summary.items()])
        csv_file(data/'stage_metrics.csv',history);csv_file(data/'cu_area_by_z.csv',areas)
        dump(data/'controls.json',dict(known_prism=known,analytic_resistance_ohm=analytic,open_control=opened))
        dump(data/'measurement_geometry.json',dict(prebond_height_nm=height*dx,gap_nm=gap*dx,interface_z_nm=shift*dx,
            xz_y_index=iy,xz_y_nm=float(y[iy]),dx_nm=dx,shape=list(shape),axis='C-order [X,Y,Z]'))
        execution.update(state='COMPLETE',finished_at_utc=now());dump(data/'validation.json',checks)
        dump(out/'execution.json',execution)
        print(json.dumps(dict(state=execution['state'],summary=summary,checks_passed=sum(v=='PASS' for v in checks.values())),indent=2),flush=True)
    except Exception as exc:
        execution.update(state='FAILED',finished_at_utc=now(),error=f'{type(exc).__name__}: {exc}')
        dump(out/'execution.json',execution);dump(data/'validation.json',checks)
        raise

if __name__=='__main__':main()
