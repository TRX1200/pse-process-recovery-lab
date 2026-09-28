"""Serve the built simulator UI and validated local simulation endpoints.

Run ``python sim_app/server.py`` after building ``sim_app/frontend``.
The server binds only to the local machine by default. No external service,
credentials, database, or remotely generated scientific response is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import math
from pathlib import Path
import sys
import threading
from typing import Any
from urllib.parse import unquote, urlsplit

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP_DIR = Path(__file__).resolve().parent
DIST_DIR = APP_DIR / "frontend" / "dist"
MAX_BODY_BYTES = 128 * 1024
MAX_SWEEP_POINTS = 21
SIMULATION_SLOTS = threading.BoundedSemaphore(2)
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
    return {"app": "Process Studio", "version": "0.1.0", "models": models}


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


class Handler(BaseHTTPRequestHandler):
    server_version = "ProcessStudio/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"{self.log_date_time_string()} {format % args}\n")

    def send_json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # The requesting browser disconnected; no computation error is hidden.
            return

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/api/health":
            self.send_json(HTTPStatus.OK, {"status": "ok", "version": "0.1.0"})
            return
        if path == "/api/schema":
            self.send_json(HTTPStatus.OK, schema())
            return
        if path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown API endpoint"})
            return
        candidate = (DIST_DIR / path.lstrip("/")).resolve()
        if not candidate.is_relative_to(DIST_DIR.resolve()):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if path == "/":
            candidate = DIST_DIR / "index.html"
        if not candidate.is_file():
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "UI not built or file missing. Build sim_app/frontend first."})
            return
        content_types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                         ".ico": "image/x-icon", ".woff2": "font/woff2", ".json": "application/json"}
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_types.get(candidate.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        routes = {"/api/simulate": simulate_request, "/api/sweep": sweep_request}
        if path not in routes:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown API endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length"})
            return
        if not 0 < length <= MAX_BODY_BYTES:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Invalid or oversized request body"})
            return
        # Incomplete clients must not hold the scarce computation slots.
        self.connection.settimeout(10.0)
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request body")
            payload = json.loads(body.decode("utf-8"))
        except TimeoutError:
            self.send_json(HTTPStatus.REQUEST_TIMEOUT, {"error": "Request body timed out"})
            return
        except (ValueError, UnicodeDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if not SIMULATION_SLOTS.acquire(blocking=False):
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Simulation busy; retry shortly"})
            return
        try:
            response = routes[path](payload)
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            # Surface a failed computation, and preserve the actual traceback in server logs.
            import traceback
            traceback.print_exc()
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Simulation failed: {type(exc).__name__}"})
        else:
            self.send_json(HTTPStatus.OK, response)
        finally:
            SIMULATION_SLOTS.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    schema()  # Fail before serving if the model modules cannot be loaded.
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Process Studio: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
