"""Exercise the actual HTTP handler and persisted process-flow result."""
import functools
import http.client
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from flow_lab.model import presets
from flow_lab.service import run_request
from rf_lab.server import Handler


class FlowHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch('flow_lab.service.run_request', functools.partial(run_request, root=self.temp.name))
        self.patch.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)
        self.patch.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            conn.request(method, path, json.dumps(body) if body is not None else None,
                         headers or {'Content-Type': 'application/json'})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_schema_and_sequence_roundtrip(self):
        status, schema = self.request('GET', '/api/flow/schema')
        self.assertEqual(status, 200)
        self.assertTrue(schema['available'])
        recipe = {k: v for k, v in presets()[0].items() if k != 'id'}
        status, result = self.request('POST', '/api/flow/simulate', recipe)
        self.assertEqual(status, 200)
        self.assertEqual(len(result['frames']), len(recipe['steps']) + 1)
        self.assertEqual(result['frames'][5]['metrics']['si_components_above_zero'], 3)
        path = Path(self.temp.name) / result['run_id'] / 'result.json'
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), result)

    def test_invalid_recipe_and_cross_origin_do_not_persist(self):
        for payload in ({'unknown': 1}, {'domain': {}, 'steps': []}, None):
            self.assertEqual(self.request('POST', '/api/flow/simulate', payload)[0], 400)
        status, _ = self.request('POST', '/api/flow/simulate', {},
                                {'Content-Type': 'application/json', 'Origin': 'https://example.invalid'})
        self.assertEqual(status, 403)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
