"""HTTP boundary checks use an ephemeral loopback port and owned temp jobs."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from native_lab.jobs import JobManager
from native_lab.server import Handler


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = JobManager(self.temp.name)
        class TestHandler(Handler):
            def log_message(self, *_):
                pass
        TestHandler.manager = self.manager
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.manager.close()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_invalid_geometry_and_remote_origins_cannot_start_jobs(self):
        status, _ = self.request("POST", "/api/native/jobs", '{}',
                                 {"Content-Type": "application/json", "Origin": "https://example.com"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/native/jobs", '{}')
        self.assertEqual(status, 415)
        status, _ = self.request("POST", "/api/native/jobs",
                                 json.dumps({"model": "etch", "params": {"width_nm": 350}}),
                                 {"Content-Type": "application/json"})
        self.assertEqual(status, 400)
        self.assertEqual(self.manager.recent(), [])

    def test_schema_and_owned_job_cancel_roundtrip(self):
        status, schema = self.request("GET", "/api/native/schema")
        self.assertEqual(status, 200)
        self.assertTrue(schema["available"])
        status, job = self.request("POST", "/api/native/jobs", '{"model":"etch"}',
                                   {"Content-Type": "application/json"})
        self.assertEqual(status, 202)
        status, cancelled = self.request("POST", f'/api/native/jobs/{job["id"]}/cancel', '{}',
                                         {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["state"], "cancelled")
        status, _ = self.request("GET", f'/api/native/jobs/{job["id"]}/result')
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
