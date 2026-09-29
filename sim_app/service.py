"""Validated process operations shared by the local API and browser Python."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from typing import Any

APP_VERSION = "0.4.0"
MAX_SWEEP_POINTS = 21
MODEL_LABELS = {"ald": "ALD", "etch": "Plasma Etch"}


def get_model(name: str) -> Any:
    if name not in MODEL_LABELS:
        raise ValueError("model must be 'ald' or 'etch'")
    return importlib.import_module(f"sim_app.models.{name}")


def schema() -> dict[str, Any]:
    models = {}
    for name, label in MODEL_LABELS.items():
        module = get_model(name)
        models[name] = {
            "label": label,
            "params": module.PARAMS,
            "faults": module.FAULTS,
            "model_version": module.MODEL_VERSION,
        }
    return {"app": "Process Studio", "version": APP_VERSION, "models": models}


def parse_request(payload: Any, *, sweep: bool = False) -> tuple[str, Any, dict, str]:
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object")
    allowed = {"model", "params", "fault"}
    if sweep:
        allowed |= {"parameter", "values"}
    if set(payload) - allowed:
        raise ValueError("Unknown request fields: " + ", ".join(sorted(set(payload) - allowed)))
    name = payload.get("model")
    if not isinstance(name, str):
        raise ValueError("A model name is required")
    module = get_model(name)
    raw = payload.get("params", {})
    if not isinstance(raw, dict):
        raise ValueError("params must be an object")
    specs = {item["key"]: item for item in module.PARAMS}
    unknown = set(raw) - set(specs)
    if unknown:
        raise ValueError("Unknown parameters: " + ", ".join(sorted(unknown)))
    params = {key: item["default"] for key, item in specs.items()}
    params.update(raw)
    for key, value in params.items():
        spec = specs[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a finite number")
        if not spec["min"] <= value <= spec["max"]:
            raise ValueError(f"{key} must be within [{spec['min']}, {spec['max']}]")
        if not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        # Numerically identical JSON integers/floats identify the same recipe.
        params[key] = float(value)
    fault = payload.get("fault", "none")
    if not isinstance(fault, str) or fault not in {item["id"] for item in module.FAULTS}:
        raise ValueError("Unknown fault for this model")
    return name, module, params, fault


def ensure_finite_json(value: Any) -> None:
    """Reject non-finite/model-specific objects rather than emitting invalid JSON."""
    json.dumps(value, allow_nan=False)


def simulate_request(payload: Any) -> dict[str, Any]:
    name, module, params, fault = parse_request(payload)
    result = module.simulate(params, fault=fault)
    baseline = module.simulate(params, fault="none") if fault != "none" else None
    identity = {"model": name, "model_version": module.MODEL_VERSION, "params": params, "fault": fault}
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    response = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": name,
        "params": params,
        "fault": fault,
        "result": result,
        "baseline": baseline,
        "baseline_definition": "Same recipe with no injected fault; not experimental ground truth.",
    }
    ensure_finite_json(response)
    return response


def sweep_request(payload: Any) -> dict[str, Any]:
    name, module, params, fault = parse_request(payload, sweep=True)
    parameter = payload.get("parameter")
    specs = {item["key"]: item for item in module.PARAMS}
    if not isinstance(parameter, str) or parameter not in specs:
        raise ValueError("Unknown sweep parameter")
    values = payload.get("values")
    if not isinstance(values, list) or not 2 <= len(values) <= MAX_SWEEP_POINTS:
        raise ValueError(f"Sweep requires 2 to {MAX_SWEEP_POINTS} values")
    requests = []
    # Validate every sample before executing any work.
    for value in values:
        item = {"model": name, "params": {**params, parameter: value}, "fault": fault}
        parse_request(item)
        requests.append(item)
    runs = []
    for item in requests:
        result = module.simulate(item["params"], fault=fault)
        runs.append({"input": item["params"][parameter], "metrics": result["metrics"],
                     "diagnostics": result.get("diagnostics", []),
                     "effective": result.get("effective", {})})
    response = {"model": name, "model_version": module.MODEL_VERSION,
                "parameter": parameter, "unit": specs[parameter]["unit"],
                "params": params, "fault": fault, "runs": runs}
    ensure_finite_json(response)
    return response
