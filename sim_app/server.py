"""Serve the built simulator UI and validated local simulation endpoints.

Run ``python sim_app/server.py`` after building ``sim_app/frontend``.
The server binds only to the local machine by default. No external service,
credentials, database, or remotely generated scientific response is used.
"""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from typing import Any
from urllib.parse import unquote, urlsplit

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim_app.service import APP_VERSION, schema, simulate_request, sweep_request

APP_DIR = Path(__file__).resolve().parent
DIST_DIR = APP_DIR / "frontend" / "dist"
MAX_BODY_BYTES = 128 * 1024
SIMULATION_SLOTS = threading.BoundedSemaphore(2)


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
            self.send_json(HTTPStatus.OK, {"status": "ok", "version": APP_VERSION})
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
                         ".pdf": "application/pdf", ".ico": "image/x-icon", ".woff2": "font/woff2", ".json": "application/json"}
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
