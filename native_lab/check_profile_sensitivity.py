"""Small numerical control study; not physical calibration or full convergence."""
import json
from pathlib import Path
from native_lab.engine import simulate
from native_lab.storage import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    (ROOT/'docs/validation').mkdir(parents=True,exist_ok=True)
    rows = []
    for model in ('etch','ald'):
        baseline = json.loads((ROOT/f'sim_app/frontend/public/native/{model}-ripple.json').read_text(encoding='utf-8'))
        for label, overrides in [('baseline',None), ('grid_4nm',{'grid_nm':4}),
                                 ('seed_plus_1',{'seed':baseline['params']['seed']+1}),
                                 ('rays_600',{'rays_per_point':600})]:
            result = baseline if overrides is None else simulate({'model':model,'params':{**baseline['params'],**overrides}})
            initial, final = result['frames'][0]['metrics'], result['frames'][-1]['metrics']
            rows.append(dict(model=model,case=label,params=result['params'],run_hash=result['run_hash'],
                             implementation=result['implementation'],environment=result['environment'],numerics=result['numerics'],
                             initial_rq_nm=initial['roughness_rq_nm'],final_rq_nm=final['roughness_rq_nm'],
                             delta_rq_nm=final['roughness_rq_nm']-initial['roughness_rq_nm'],
                             mean_advance_nm=final['mean_advance_nm']))
            print(model,label,rows[-1]['delta_rq_nm'],flush=True)
    write_json(ROOT/'docs/validation/profile_sensitivity.json',dict(
        evidence='numerical sensitivity; not physical validation',
        command='python -m native_lab.check_profile_sensitivity',
        scope='Planar ripple only; two grids, two seeds, two ray counts. Not a converged continuum extrapolation.',
        rows=rows))


if __name__ == '__main__':
    main()
