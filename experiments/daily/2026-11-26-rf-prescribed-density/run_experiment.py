"""Run validated, fixed-input RF point solves without calling tune/simulate.

Python 3.12 + requirements.txt. Replay: python run_experiment.py --out NEW_DIR
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source_snapshot'))
import numpy as np
from rf_lab.model import validate, point

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):
    raw=json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False).encode('utf-8')
    p.write_bytes(gzip.compress(raw,mtime=0) if p.suffix=='.gz' else raw)
def csv_file(p,rows):
    with (gzip.open(p,'wt',newline='',encoding='utf-8') if p.suffix=='.gz' else p.open('w',newline='',encoding='utf-8')) as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def flatten(case,result):
    row=dict(case=case)
    for key,value in result.items():
        if isinstance(value,list):
            row[key+'_real']=value[0];row[key+'_imag']=value[1]
        else: row[key]=value
    return row

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=HERE)
    out=parser.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=out/'data';data.mkdir(exist_ok=False)
    plan=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    for rel,expected in plan['source_sha256'].items(): assert sha(HERE/'source_snapshot'/rel)==expected
    versions={k:importlib.metadata.version(k) for k in plan['versions']};assert versions==plan['versions']
    config=plan['frequency_grid']
    freq=config['center_mhz']+config['offset_step_mhz']*np.arange(config['offset_integer_min'],config['offset_integer_max']+1)
    execution=dict(execution_id=uuid.uuid4().hex,server_job_id=None,
        id_kind='Generated experiment ID; direct point() calls, not a server job ID',
        scheduled_at_kst=plan['scheduled_at_kst'],started_at_utc=now(),plan_sha256=sha(HERE/'plan.json'),
        versions={**versions,'python':platform.python_version()},historical_results_reused=False,state='RUNNING',runs={})
    dump(out/'execution.json',execution);checks={}
    def check(name,condition):
        checks[name]='PASS' if bool(condition) else 'FAIL'
        if not condition: raise AssertionError(name)
    try:
        a,b=plan['cases']['A'],plan['cases']['B']
        check('only_prescribed_density_changed',[k for k in a if a[k]!=b[k]]==['density_1e15_m3'])
        check('frequency_grid',len(freq)==201 and np.allclose(np.diff(freq),.05,rtol=0,atol=1e-12) and freq[100]==13.56)
        runs={};summary={};all_rows=[];operating_rows=[];controls={};max_residual=0
        for case,p in plan['cases'].items():
            started=now();p=validate(p)
            band=[point(validate({**p,'frequency_mhz':float(f)})) for f in freq]
            op=point(p)
            check(case+'_operating_point_in_band',op==band[100])
            replay=[point(validate({**p,'frequency_mhz':float(f)})) for f in freq]
            check(case+'_exact_replay',band==replay)
            for r in band:
                values=[v for v in flatten(case,r).values() if isinstance(v,(int,float))]
                check(case+'_finite_values',np.isfinite(values).all())
                check(case+'_passivity',r['z_generator'][0]>0 and 0<=r['reflected_pct']<=100+1e-10 and
                      all(r[k]>=0 for k in ['reflected_w','bulk_w','coil_loss_w','capacitor_loss_w']))
                check(case+'_power_balance',abs(r['power_residual_w'])<1e-8)
                gamma=complex(*r['gamma'])
                check(case+'_amplitude_power_conversion',abs(r['reflected_w']-p['forward_w']*abs(gamma)**2)<1e-9)
                max_residual=max(max_residual,abs(r['power_residual_w']))
                all_rows.append(flatten(case,r))
            diagnostic=min(band,key=lambda r:r['reflected_pct'])
            coil_r=2*math.pi*p['frequency_mhz']*1e6*p['coil_uh']*1e-6/p['coil_q']
            summary[case]=dict(density_1e15_m3=p['density_1e15_m3'],operating_point=op,coil_r_ohm_at_operating_point=coil_r,
                sampled_band_minimum=dict(frequency_mhz=diagnostic['frequency_mhz'],reflected_pct=diagnostic['reflected_pct'],
                    s11_db=diagnostic['s11_db'],note='Minimum only among the predeclared 201 samples; no optimizer or grid refinement'))
            operating_rows.append(dict(density_1e15_m3=p['density_1e15_m3'],coil_r_ohm=coil_r,**flatten(case,op)))
            runs[case]=dict(inputs=p,operating_point=op,frequency_sweep=band)
            dump(data/f'{case}.json.gz',runs[case])
            execution['runs'][case]=dict(started_at_utc=started,finished_at_utc=now(),
                config_sha256=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),raw_sha256=sha(data/f'{case}.json.gz'),
                frequency_points=len(band),exact_replay=True)
            zero=point(validate({**p,'forward_w':0}));half=point(validate({**p,'forward_w':p['forward_w']/2}));no_line=point(validate({**p,'cable_m':0}))
            powers=['reflected_w','accepted_w','bulk_w','coil_loss_w','capacitor_loss_w']
            check(case+'_zero_power',all(zero[k]==0 for k in powers) and zero['bulk_efficiency_pct'] is None)
            check(case+'_power_scaling',all(np.isclose(half[k],op[k]/2,rtol=1e-12,atol=1e-10) for k in powers) and
                  np.isclose(half['coil_current_rms_a'],op['coil_current_rms_a']/math.sqrt(2),rtol=1e-12))
            check(case+'_lossless_line_invariance',all(np.isclose(no_line[k],op[k],rtol=1e-12,atol=1e-9) for k in powers))
            controls[case]=dict(zero_power=zero,half_power=half,zero_length_feed=no_line)
        check('inverse_density_bulk_scaling_and_fixed_sheath',all(np.isclose(rb['bulk_r_ohm'],ra['bulk_r_ohm']*2/3,rtol=1e-12) and np.isclose(rb['bulk_l_nh'],ra['bulk_l_nh']*2/3,rtol=1e-12) and rb['sheath_c_pf']==ra['sheath_c_pf'] for ra,rb in zip(runs['A']['frequency_sweep'],runs['B']['frequency_sweep'])))
        check('snapshot_hashes_unchanged',all(sha(HERE/'source_snapshot'/rel)==v for rel,v in plan['source_sha256'].items()))
        checks.update(max_abs_power_residual_w=max_residual,physical_calibration='NOT_RUN',frequency_grid_refinement='NOT_RUN',
            plasma_self_consistency='NOT_MODELED',component_parasitics_and_temperature='NOT_MODELED',process_outcome='NOT_MODELED')
        csv_file(data/'frequency_sweep.csv.gz',all_rows);csv_file(data/'operating_points.csv',operating_rows)
        dump(data/'summary.json',summary);dump(data/'controls.json',controls);dump(data/'validation.json',checks)
        execution.update(state='COMPLETE',finished_at_utc=now());dump(out/'execution.json',execution)
        print(json.dumps(dict(state=execution['state'],summary=summary,validation=checks),indent=2),flush=True)
    except Exception as exc:
        execution.update(state='FAILED',finished_at_utc=now(),error=f'{type(exc).__name__}: {exc}')
        dump(out/'execution.json',execution);dump(data/'validation.json',checks);raise

if __name__=='__main__': main()
