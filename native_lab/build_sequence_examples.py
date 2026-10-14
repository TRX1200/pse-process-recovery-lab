"""Recompute the public native sequence examples with explicit inputs."""
from pathlib import Path
from native_lab.sequence import simulate
from native_lab.schema import schema
from native_lab.storage import write_json


def main():
    target = Path(__file__).resolve().parents[1]/'sim_app/frontend/public/native'
    target.mkdir(parents=True, exist_ok=True)
    write_json(target/'schema.json', schema())
    base = {'duration_s': 5, 'cycles': 160, 'rays_per_point': 300}
    for name, overrides in [('reference', {}), ('short-pulse', {'pulse_s': .001}),
                            ('wide-angle', {'ion_exponent': 20})]:
        result = simulate({'model': 'sequence', 'params': {**base, **overrides}})
        write_json(target/f'sequence-{name}.json', result)
        print(name, result['elapsed_s'], result['etch']['frames'][-1]['metrics'],
              result['ald']['frames'][-1]['metrics'], flush=True)


if __name__ == '__main__':
    main()
