from pathlib import Path
from native_lab.storage import write_json
from rf_lab.model import simulate, schema
from rf_lab.coupled import simulate as simulate_coupled, FIELDS, VERSION


def main():
    target = Path(__file__).resolve().parents[1]/'sim_app/frontend/public/rf'
    target.mkdir(parents=True, exist_ok=True)
    write_json(target/'schema.json', schema())
    write_json(target/'reference.json', simulate({}))
    write_json(target/'lossy.json', simulate({'coil_q': 15}))
    write_json(target/'coupled-schema.json',{'fields':FIELDS,'version':VERSION})
    write_json(target/'coupled-reference.json',simulate_coupled({'rf_params':{}}))
    write_json(target/'coupled-lossy.json',simulate_coupled({'rf_params':{'coil_q':15}}))
    print('Calculated RF reference and lossy-coil examples')


if __name__ == '__main__':
    main()
