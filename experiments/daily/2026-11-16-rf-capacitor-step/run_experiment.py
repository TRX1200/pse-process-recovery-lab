"""Execute the predeclared A/B experiment with an exact frozen source snapshot.

Run: python run_experiment.py --out rerun
Dependencies: numpy, scipy. The original run used the versions in manifest.json.
This runner does not call the matching optimizer or modify the live application.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import platform
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'source_snapshot'))
import numpy as np
import scipy
from rf_lab.practice import simulate
from rf_lab.model import point


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():
        raise SystemExit('Preserving existing result; choose a new --out directory.')
    plan=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    for relative,expected in plan['source_hashes'].items():
        assert hashlib.sha256((HERE/'source_snapshot'/relative).read_bytes()).hexdigest()==expected
    started=datetime.now(timezone.utc).isoformat()
    a=simulate(plan['conditions']['A']);b=simulate(plan['conditions']['B'])
    assert a['rows']==simulate(plan['conditions']['A'])['rows']
    assert b['rows']==simulate(plan['conditions']['B'])['rows']
    assert a['rows'][:100]==b['rows'][:100]
    for ra,rb in zip(a['rows'],b['rows']):
        for key in ['t_s','density_1e15_m3','sheath_mm','load_r_ohm','load_x_ohm','cs_pf']:
            assert ra[key]==rb[key],key
        assert rb['fixed_pct']==ra['reflected_pct']
    rows=[];summary={}
    for name,result in [('A',a),('B',b)]:
        for row in result['rows']:
            p={**result['circuit_inputs'],'density_1e15_m3':row['density_1e15_m3'],'sheath_total_mm':row['sheath_mm']}
            sample=point(p,cp_pf=row['cp_pf'],cs_pf=row['cs_pf'])
            enriched={**row,'case':name,'input_r_ohm':sample['z_generator'][0],'input_x_ohm':sample['z_generator'][1],
                'gamma_real':sample['gamma'][0],'gamma_imag':sample['gamma'][1],
                'accepted_w':sample['accepted_w'],'coil_current_rms_a':sample['coil_current_rms_a'],
                'series_cap_rms_v':sample['series_cap_rms_v']}
            assert np.isfinite([v for v in enriched.values() if isinstance(v,(int,float))]).all()
            assert -1e-10<=enriched['reflected_pct']<=100+1e-10
            assert abs(enriched['power_residual_w'])<1e-8
            assert all(enriched[k]>=0 for k in ['bulk_w','coil_loss_w','capacitor_loss_w','reflected_w'])
            rows.append(enriched)
        selected=[r for r in rows if r['case']==name and 10<=r['t_s']<=20]
        times=np.array([r['t_s'] for r in selected])
        assert len(times)==101 and np.allclose(np.diff(times),.1)
        means={k:float(np.trapezoid([r[k] for r in selected],times)/10) for k in
            ['reflected_pct','reflected_w','accepted_w','bulk_w','coil_loss_w','capacitor_loss_w']}
        means['bulk_efficiency_pct']=means['bulk_w']/300*100
        summary[name]=dict(time_mean_10_to_20_s=means,
            at_10_s={k:selected[0][k] for k in ['reflected_pct','bulk_w','input_r_ohm','input_x_ohm']},
            at_20_s={k:selected[-1][k] for k in ['reflected_pct','bulk_w','input_r_ohm','input_x_ohm']})
    zero=simulate({**plan['conditions']['A'],'power_w':0})
    assert all(r[k]==0 for r in zero['rows'] for k in ['reflected_w','bulk_w','coil_loss_w','capacitor_loss_w'])
    static=simulate({**plan['conditions']['A'],'sigma':0})
    assert len({r['reflected_pct'] for r in static['rows']})==1
    max_residual=max(abs(r['power_residual_w']) for r in rows)
    checks=dict(same_seed_exact_replay='PASS',same_prescribed_load='PASS',history_before_10s_equal='PASS',
        fixed_counterfactual_matches_A='PASS',finite_values='PASS',passive_powers='PASS',
        zero_power_control='PASS',zero_noise_static_control='PASS',power_balance='PASS',
        max_abs_power_residual_w=max_residual,physical_validation='NOT_PERFORMED',
        seed_ensemble_sensitivity='NOT_RUN: one fixed-seed load realization',
        time_step_convergence='NOT_RUN: quasi-static samples at 0.1 s; not an RF transient solver')
    result=dict(experiment_id=plan['experiment_id'],execution_id=uuid.uuid4().hex,
        job_id=None,execution_id_note='Direct function execution; no server job ID was issued.',
        started_at_utc=started,finished_at_utc=datetime.now(timezone.utc).isoformat(),
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        cases={'A':a,'B':b},summary=summary,checks=checks)
    dump(out/'result.json',result);dump(out/'summary.json',summary);dump(out/'checks.json',checks)
    with (out/'time_series.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({'execution_id':result['execution_id'],'summary':summary,'checks':checks},indent=2,ensure_ascii=False))


if __name__=='__main__':main()
