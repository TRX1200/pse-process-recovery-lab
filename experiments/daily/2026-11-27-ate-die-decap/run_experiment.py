"""Execute the predeclared PDN comparison using the unchanged source snapshot.

Replay: python run_experiment.py --out NEW_DIRECTORY
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

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source_snapshot'))
import numpy as np
from fab_lab.ate import simulate

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def csv_file(p,rows):
    with (gzip.open(p,'wt',newline='',encoding='utf-8') if p.suffix=='.gz' else p.open('w',newline='',encoding='utf-8')) as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def nodal_control(f_hz,c_nf,fixture):
    """Independent two-node KCL solve; source topology/values frozen in plan."""
    jw=2j*np.pi*f_hz
    vrm,bc,link,dc=[fixture[k] for k in ['vrm','board_cap','link','die_cap']]
    zv=vrm['r_ohm']+jw*vrm['l_h']
    zb=bc['r_ohm']+jw*bc['l_h']+1/(jw*bc['c_f'])
    zl=link['r_ohm']+jw*link['l_h']
    zd=dc['r_ohm']+jw*dc['l_h']+1/(jw*c_nf*1e-9)
    y=np.array([[1/zv+1/zb+1/zl,-1/zl],[-1/zl,1/zd+1/zl]],dtype=complex)
    source=np.array([0.,1.],dtype=complex)
    v=np.linalg.solve(y,source)
    iv,ib,il,idie=v[0]/zv,v[0]/zb,(v[1]-v[0])/zl,v[1]/zd
    dissipated=abs(iv)**2*vrm['r_ohm']+abs(ib)**2*bc['r_ohm']+abs(il)**2*link['r_ohm']+abs(idie)**2*dc['r_ohm']
    return dict(z_real_ohm=float(v[1].real),z_imag_ohm=float(v[1].imag),z_abs_ohm=float(abs(v[1])),
        max_kcl_residual_a=float(np.max(np.abs(y@v-source))),input_power_w=float(v[1].real),
        resistor_power_w=float(dissipated),power_residual_w=float(v[1].real-dissipated))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=HERE)
    out=parser.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=out/'data';data.mkdir(exist_ok=False)
    plan=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    for rel,h in plan['source_sha256'].items():assert sha(HERE/'source_snapshot'/rel)==h,rel
    versions={k:importlib.metadata.version(k) for k in plan['versions']};assert versions==plan['versions']
    execution=dict(execution_id=uuid.uuid4().hex,server_job_id=None,
        id_kind='Generated experiment ID; direct engine calls, not a server job ID',
        scheduled_at_kst=plan['scheduled_at_kst'],started_at_utc=now(),state='RUNNING',
        plan_sha256=sha(HERE/'plan.json'),versions={**versions,'python':platform.python_version()},
        historical_results_reused=False,runs={})
    dump(out/'execution.json',execution);checks={}
    def check(name,condition):
        checks[name]='PASS' if bool(condition) else 'FAIL'
        if not condition:raise AssertionError(name)
    try:
        a,b=plan['cases']['A'],plan['cases']['B']
        check('only_decap_changed',[k for k in a if a[k]!=b[k]]==['decap_nf'])
        rows=[];controls=[];summary={};runs={}
        max_mag_error=max_kcl=max_power=0.
        for case,p in plan['cases'].items():
            started=now();r=simulate(p);replay=simulate(p);runs[case]=r
            check(case+'_exact_replay',r==replay)
            check(case+'_input_preserved',r['config']==p)
            f=np.array(r['x']);z=np.array(r['traces'][0])
            expected=np.geomspace(1e5,3e9,241)/1e6
            check(case+'_frequency_and_units',np.array_equal(f,expected) and r['x_unit']=='MHz' and r['y_unit']=='Ω')
            check(case+'_finite_positive',len(r['traces'])==1 and len(z)==len(f) and np.isfinite(z).all() and (z>0).all())
            peak=int(np.argmax(z));mask=(f>=plan['analysis_band_mhz'][0])&(f<=plan['analysis_band_mhz'][1])
            subset=np.flatnonzero(mask);midpeak=int(subset[np.argmax(z[mask])])
            reading=list(r['reading'].values())
            check(case+'_engine_maximum_readback',reading==[float(z[peak]),float(f[peak])])
            probes=[]
            for target in plan['probe_nominal_mhz']:
                k=int(np.argmin(abs(f-target)))
                probes.append(dict(nominal_mhz=target,sample_index=k,actual_mhz=float(f[k]),z_abs_ohm=float(z[k])))
            summary[case]=dict(decap_nf=p['decap_nf'],port=r['port'],
                full_band_max=dict(z_abs_ohm=float(z[peak]),frequency_mhz=float(f[peak]),at_endpoint=bool(peak in (0,len(f)-1))),
                analysis_band_max=dict(z_abs_ohm=float(z[midpeak]),frequency_mhz=float(f[midpeak]),sample_count=int(mask.sum()),
                    actual_first_mhz=float(f[subset[0]]),actual_last_mhz=float(f[subset[-1]])),probes=probes)
            for i,(fm,zm) in enumerate(zip(f,z)):
                control=nodal_control(fm*1e6,p['decap_nf'],plan['fixture'])
                error=abs(control['z_abs_ohm']-zm)
                max_mag_error=max(max_mag_error,error);max_kcl=max(max_kcl,control['max_kcl_residual_a'])
                max_power=max(max_power,abs(control['power_residual_w']))
                check(case+'_independent_nodal_agreement',error<1e-12)
                check(case+'_positive_real_impedance',control['z_real_ohm']>0)
                check(case+'_kcl',control['max_kcl_residual_a']<1e-10)
                check(case+'_power_balance',abs(control['power_residual_w'])<1e-10)
                rows.append(dict(case=case,decap_nf=p['decap_nf'],frequency_mhz=float(fm),z_abs_ohm=float(zm)))
                controls.append(dict(case=case,frequency_mhz=float(fm),**control,engine_abs_error_ohm=float(error)))
            changed_seed=simulate({**p,'seed':43})
            check(case+'_unused_seed_invariance',changed_seed['traces']==r['traces'] and changed_seed['x']==r['x'])
            dc=nodal_control(1.,p['decap_nf'],plan['fixture'])
            check(case+'_low_frequency_limit',abs(dc['z_abs_ohm']-.037)<1e-8)
            dump(data/f'{case}.json',r)
            execution['runs'][case]=dict(started_at_utc=started,finished_at_utc=now(),raw_sha256=sha(data/f'{case}.json'),
                config_sha256=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),frequency_points=len(f),
                exact_replay=True,low_frequency_control_1hz=dc)
        check('identical_frequency_grids',runs['A']['x']==runs['B']['x'])
        check('source_snapshot_unchanged',all(sha(HERE/'source_snapshot'/r)==h for r,h in plan['source_sha256'].items()))
        check('only_normalized_decap_changed',[k for k in runs['A']['config'] if runs['A']['config'][k]!=runs['B']['config'][k]]==['decap_nf'])
        z_a=np.array(runs['A']['traces'][0]);z_b=np.array(runs['B']['traces'][0])
        comparison=[dict(frequency_mhz=fm,a_ohm=za,b_ohm=zb,b_minus_a_ohm=zb-za,b_over_a=zb/za)
                    for fm,za,zb in zip(runs['A']['x'],z_a,z_b)]
        summary['comparison']=dict(b_lower_samples=int(np.count_nonzero(z_b<z_a-1e-12)),
            b_higher_samples=int(np.count_nonzero(z_b>z_a+1e-12)),total_samples=len(z_a),
            note='Counts on a nonuniform log-frequency grid, not frequency bandwidth fractions')
        checks.update(max_abs_independent_error_ohm=max_mag_error,max_kcl_residual_a=max_kcl,max_abs_power_residual_w=max_power,
            physical_calibration='NOT_RUN',frequency_grid_refinement='NOT_RUN',component_tolerance_ensemble='NOT_RUN',
            fab_geometry_extraction='NOT_MODELED',voltage_droop_transient='NOT_MODELED',active_vrm_control='NOT_MODELED')
        csv_file(data/'frequency_response.csv',rows);csv_file(data/'comparison.csv',comparison)
        csv_file(data/'nodal_controls.csv.gz',controls)
        dump(data/'summary.json',summary);dump(data/'validation.json',checks)
        execution.update(state='COMPLETE',finished_at_utc=now());dump(out/'execution.json',execution)
        print(json.dumps(dict(state=execution['state'],summary=summary,validation=checks),indent=2))
    except Exception as exc:
        execution.update(state='FAILED',finished_at_utc=now(),error=f'{type(exc).__name__}: {exc}')
        dump(out/'execution.json',execution);dump(data/'validation.json',checks);raise

if __name__=='__main__':main()
