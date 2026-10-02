"""Calculate public examples with the pinned native engine; never fabricate frames."""
from pathlib import Path
from native_lab.engine import simulate
from native_lab.schema import schema
from native_lab.storage import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "sim_app" / "frontend" / "public" / "native"
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "schema.json", schema())
    cases = [
        ("etch-reference", "etch", {}),
        ("etch-variant", "etch", {"ion_exponent": 20, "oxygen_flux": 20}),
        ("ald-reference", "ald", {}),
        ("ald-variant", "ald", {"pulse_s": 0.002}),
    ]
    for name, model, params in cases:
        print(f"Computing {name}", flush=True)
        result = simulate({"model": model, "params": params})
        write_json(target / f"{name}.json", result)
        print(name, result["elapsed_s"], result["frames"][-1]["metrics"], flush=True)


if __name__ == "__main__":
    main()
