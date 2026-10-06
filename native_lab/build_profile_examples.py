"""Generate solved corrugation examples without replacing the original baselines."""
from pathlib import Path
from native_lab.engine import simulate
from native_lab.schema import schema
from native_lab.storage import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT/'sim_app/frontend/public/native'
    write_json(target/'schema.json',schema())
    for model in ['etch','ald']:
        for name,mode in [('ripple',1),('scallop',2)]:
            params = dict(surface_profile=mode,grid_nm=2,rays_per_point=300,
                          corrugation_amplitude_nm=8,corrugation_count=3,
                          depth_nm=240,width_nm=120)
            params.update(dict(duration_s=.15,output_steps=6) if model=='etch' else dict(cycles=40,bundle_cycles=7))
            print('Calculating',model,name,flush=True)
            result = simulate({'model':model,'params':params})
            write_json(target/f'{model}-{name}.json',result)
            print(result['elapsed_s'],result['frames'][-1]['metrics'],flush=True)


if __name__ == '__main__':
    main()
