"""Run the predeclared GAA release comparison with the frozen material-grid model."""
from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy
import argparse
import csv
import gzip
import hashlib
import json
import platform
import sys
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source_snapshot'))
import numpy as np
import scipy
from fab_lab.engine import simulate, State
from fab_lab.schema import step

def dump(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def decode(frame,shape):
    encoded=np.array(frame['grid'],dtype=np.int64)
    assert len(encoded)%2==0 and np.all(encoded[1::2]>0)
    assert np.sum(encoded[1::2])==np.prod(shape)
    values=np.repeat(encoded[::2],encoded[1::2])
    assert np.all((values>=0)&(values<=7))
    return values.astype(np.uint8).reshape(shape,order='C')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    out=parser.parse_args().out.resolve()
    if out.exists() and any(out.iterdir()):raise SystemExit('Existing output preserved; choose an empty directory.')
    out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    for relative,digest in plan['source_sha256'].items():
        assert hashlib.sha256((HERE/'source_snapshot'/relative).read_bytes()).hexdigest()==digest
    release=plan['release_step_index_zero_based'];cases=plan['cases']
    restored=deepcopy(cases['B']);restored['steps'][release]['params']['time']=cases['A']['steps'][release]['params']['time']
    assert restored==cases['A']
    started=datetime.now(timezone.utc).isoformat()
    runs={}
    for case,request in cases.items():
        target=out/case;target.mkdir()
        runs[case]=simulate(request,directory=target)
        assert runs[case]==simulate(request),'Deterministic replay mismatch'
    assert runs['A']['frames'][:release+1]==runs['B']['frames'][:release+1]
    d=cases['A']['domain'];shape=tuple(d[k] for k in ('nx','ny','nz'));dx=d['dx'];cell_volume=dx**3
    x=(np.arange(shape[0])+.5-shape[0]/2)*dx
    y=(np.arange(shape[1])+.5-shape[1]/2)*dx
    z=(np.arange(shape[2])+.5)*dx
    roi=np.broadcast_to((np.abs(x[:,None,None])<32)&(z[None,None,:]>=d['substrate']+d['box']),shape)
    before=decode(runs['A']['frames'][release],shape)
    original_si=(before==1)&roi
    initial_sige=float(np.count_nonzero(before==2)*cell_volume)
    initial_roi_sige=float(np.count_nonzero((before==2)&roi)*cell_volume)
    assert initial_sige>0 and original_si.any()
    summary={};history=[];sections={}
    ix=shape[0]//2;iy=int(np.argmin(np.abs(y-32)))
    sections['before_yz']=before[ix];sections['before_xz']=before[:,iy]
    for case,run in runs.items():
        for frame in run['frames']:
            grid=decode(frame,shape)
            assert sum(frame['volume_nm3'].values())==np.count_nonzero(grid)*cell_volume
            for name,mid in [('Si',1),('SiGe',2),('SiO2',3)]:
                assert frame['volume_nm3'][name]==np.count_nonzero(grid==mid)*cell_volume
            history.append(dict(case=case,index=frame['index'],operation=frame['op'],label=frame['label'],
                sige_nm3=frame['volume_nm3']['SiGe'],si_nm3=frame['volume_nm3']['Si'],
                roi_sige_nm3=float(np.count_nonzero((grid==2)&roi)*cell_volume),solid_cells=frame['solid_cells']))
        final=decode(run['frames'][-1],shape)
        with np.load(out/case/'final_state.npz') as saved:
            np.testing.assert_array_equal(saved['material'],final)
            for key in saved.files:assert np.isfinite(saved[key]).all()
            mask=saved['mask'].astype(bool)
        removed=(before!=0)&(final==0)
        assert np.all((final==before)|removed),'Release must only remove material'
        assert not np.any((final!=before)&~mask[:,:,None]),'Mask-protected voxels changed'
        total=float(np.count_nonzero(final==2)*cell_volume)
        roi_remaining=float(np.count_nonzero((final==2)&roi)*cell_volume)
        assert total<=initial_sige
        params=run['request']['steps'][release]['params'];fronts=int(np.floor(params['rate']*params['time']/dx+.5))
        summary[case]=dict(release_time_s=params['time'],continuous_distance_budget_nm=params['rate']*params['time'],
            integer_front_steps=fronts,front_steps_times_dx_nm=fronts*dx,
            before_sige_nm3=initial_sige,remaining_sige_nm3=total,removed_sige_nm3=initial_sige-total,
            sige_removed_pct=100*(initial_sige-total)/initial_sige,
            roi_before_sige_nm3=initial_roi_sige,roi_remaining_sige_nm3=roi_remaining,
            roi_original_si_nm3=float(original_si.sum()*cell_volume),
            roi_retained_original_si_nm3=float(np.count_nonzero(original_si&(final==1))*cell_volume),
            roi_original_si_retained_pct=100*np.count_nonzero(original_si&(final==1))/int(original_si.sum()),
            total_si_nm3=float(np.count_nonzero(final==1)*cell_volume),
            removed_voxels=int(removed.sum()),release_warnings=run['frames'][release+1]['warnings'])
        sections[case+'_yz']=final[ix];sections[case+'_xz']=final[:,iy]

    # Controls are separate from the A/B comparison and do not search for a recipe.
    zero=deepcopy(cases['A']);zero['steps'][release]['params']['time']=0
    control=simulate(zero)
    np.testing.assert_array_equal(decode(control['frames'][-1],shape),before)
    flat=State(dict(nx=16,ny=16,nz=16,dx=4,substrate=0,box=0,active=0))
    flat.g[:,:,:6]=2
    flat.apply(step('etch',material='SiGe',mode='isotropic',rate=4,time=2,selectivity=100))
    assert np.all(flat.g[:,:,:4]==2) and np.all(flat.g[:,:,4:]==0)
    checks=dict(source_hashes='PASS',single_parameter_change='PASS',deterministic_exact_replay='PASS',
        identical_upstream_frames='PASS',rle_shape_material_ids='PASS',cell_volume_accounting='PASS',
        saved_npz_matches_report='PASS',finite_saved_arrays='PASS',mask_protection='PASS',
        removal_only_no_material_conversion='PASS',zero_time_release_control='PASS',
        planar_isotropic_two_layer_control='PASS',physical_validation='NOT_PERFORMED',
        grid_convergence='NOT_RUN for this GAA geometry; fixed 4 nm voxels',
        silicon_loss='NOT_RESOLVED below one cell; zero voxel loss is not proof of physical zero loss',
        device_electrical_prediction='NOT_RUN: no gate/compact/device electrical steps in this experiment')
    result=dict(experiment_id=plan['experiment_id'],execution_id=uuid.uuid4().hex,server_job_id=None,
        execution_note='Direct function execution; this generated experiment execution ID is not a server job ID.',
        started_at_utc=started,finished_at_utc=datetime.now(timezone.utc).isoformat(),
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        cases_summary=summary,checks=checks,
        sections=dict(yz_x_index=ix,yz_x_nm=float(x[ix]),xz_y_index=iy,xz_y_nm=float(y[iy])),
        full_results='runs.json.gz contains both complete model results and every RLE process-stage frame',
        final_state='A/final_state.npz and B/final_state.npz contain all original material/dopant/mask arrays')
    raw=json.dumps(runs,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    (out/'runs.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    assert json.loads(gzip.decompress((out/'runs.json.gz').read_bytes()))==runs
    np.savez_compressed(out/'sections.npz',**sections,x_nm=x,y_nm=y,z_nm=z)
    dump(out/'result.json',result);dump(out/'summary.json',summary);dump(out/'checks.json',checks)
    with (out/'stage_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(history[0]));writer.writeheader();writer.writerows(history)
    print(json.dumps(dict(execution_id=result['execution_id'],summary=summary,checks=checks),indent=2,ensure_ascii=False))

if __name__=='__main__':main()
