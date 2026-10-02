"""Same-origin local UI/API for the native workbench and earlier learning lab."""
from __future__ import annotations
import argparse
from http.server import ThreadingHTTPServer
import json
from urllib.parse import urlsplit
from sim_app.server import Handler as LearningHandler, MAX_BODY_BYTES
from native_lab.jobs import JobManager, BusyError
from native_lab.schema import schema


class Handler(LearningHandler):
    manager: JobManager

    def do_GET(self):
        parts = urlsplit(self.path).path.strip("/").split("/")
        if parts[:2] != ["api", "native"]:
            return super().do_GET()
        try:
            if parts == ["api", "native", "schema"]:
                self.send_json(200, {**schema(), "available": True, "execution": "local-native"})
            elif parts == ["api", "native", "jobs"]:
                self.send_json(200, {"jobs": self.manager.recent()})
            elif len(parts) == 4 and parts[2] == "jobs":
                self.send_json(200, self.manager.status(parts[3]))
            elif len(parts) == 5 and parts[2] == "jobs" and parts[4] == "result":
                self.send_json(200, self.manager.result(parts[3]))
            else:
                self.send_json(404, {"error": "Unknown native route"})
        except FileNotFoundError as exc:
            self.send_json(404, {"error": str(exc)})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})

    def do_POST(self):
        parts = urlsplit(self.path).path.strip("/").split("/")
        if parts[:2] != ["api", "native"]:
            return super().do_POST()
        # A remote website must not launch expensive local jobs cross-origin.
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.send_json(403, {"error": "Use the local workbench page"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.send_json(415, {"error": "application/json required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError("Invalid request size")
            self.connection.settimeout(10)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete body")
            payload = json.loads(body)
            if parts == ["api", "native", "jobs"]:
                self.send_json(202, self.manager.submit(payload))
            elif len(parts) == 5 and parts[2] == "jobs" and parts[4] == "cancel":
                self.send_json(200, self.manager.cancel(parts[3]))
            else:
                self.send_json(404, {"error": "Unknown native route"})
        except BusyError as exc:
            self.send_json(409, {"error": str(exc)})
        except (ValueError, UnicodeDecodeError, FileNotFoundError) as exc:
            self.send_json(400, {"error": str(exc)})
        except TimeoutError:
            self.send_json(408, {"error": "Request timed out"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    from native_lab.engine import initialize
    initialize()  # Fail visibly before claiming the native backend is available.
    Handler.manager = JobManager()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Native ALD / Etch Lab: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        Handler.manager.close()


if __name__ == "__main__":
    main()
