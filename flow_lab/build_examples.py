"""Calculate public process-flow examples using the same local geometry model."""
from pathlib import Path
from flow_lab.model import presets, schema, simulate
from native_lab.storage import write_json


def main():
    target = Path(__file__).resolve().parents[1] / "sim_app/frontend/public/flow"
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "schema.json", schema())
    for preset in presets():
        result = simulate({k: v for k, v in preset.items() if k != "id"})
        write_json(target / f"{preset['id']}.json", result)
        print(preset['id'], result['elapsed_s'], result['frames'][-1]['metrics'], flush=True)


if __name__ == "__main__":
    main()
