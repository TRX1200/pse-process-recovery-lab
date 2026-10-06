"""Unified native geometry + RF workbench, bound to loopback only."""
import argparse
from http.server import ThreadingHTTPServer
import json
import threading
from urllib.parse import urlsplit
from native_lab.server import Handler as NativeHandler
from native_lab.jobs import JobManager
from sim_app.server import MAX_BODY_BYTES
from rf_lab.model import schema
from rf_lab.service import run_request, run_coupled, recent, import_process_results

SLOTS = threading.BoundedSemaphore(2)


class Handler(NativeHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/rf/schema':
            self.send_json(200, {**schema(), 'available': True})
        elif path == '/api/rf/runs':
            self.send_json(200, {'runs': recent()})
        elif path == '/api/rf/coupled/schema':
            from rf_lab.coupled import FIELDS, VERSION
            self.send_json(200, {'fields':FIELDS,'version':VERSION})
        else:
            super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ('/api/rf/simulate', '/api/rf/coupled', '/api/rf/sync-process'):
            return super().do_POST()
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.send_json(403, {'error': 'Use the local workbench page'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send_json(415, {'error': 'application/json required'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError('Invalid request size')
            self.connection.settimeout(10)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('Incomplete body')
            payload = json.loads(body)
            if not SLOTS.acquire(blocking=False):
                return self.send_json(503, {'error': 'RF calculation busy'})
            try:
                if path == '/api/rf/sync-process':
                    import_process_results()
                    response = {'synced': True}
                elif path == '/api/rf/coupled':
                    response = run_coupled(payload)
                else:
                    response = run_request(payload)
            finally:
                SLOTS.release()
            self.send_json(200, response)
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            self.send_json(400, {'error': str(exc)})
        except TimeoutError:
            self.send_json(408, {'error': 'Request timed out'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8768)
    args = parser.parse_args()
    from native_lab.engine import initialize
    initialize()
    import_process_results()
    Handler.manager = JobManager()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'RF + Native Lab: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        Handler.manager.close()


if __name__ == '__main__':
    main()
