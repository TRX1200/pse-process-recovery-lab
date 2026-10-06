import functools
from contextlib import closing
from http.server import ThreadingHTTPServer
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from rf_lab.server import Handler
from rf_lab.service import connect, run_request, run_coupled


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root/'warehouse.sqlite'
        connect(self.database).close()
        self.run_patch = patch('rf_lab.server.run_request', functools.partial(
            run_request, database=self.database, output_root=self.root/'results'))
        self.run_patch.start()
        self.coupled_patch = patch('rf_lab.server.run_coupled', functools.partial(
            run_coupled, database=self.database, output_root=self.root/'coupled'))
        self.coupled_patch.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)
        self.run_patch.stop()
        self.coupled_patch.stop()
        self.temp.cleanup()

    def request(self, data, headers=None, path='/api/rf/simulate'):
        client = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        try:
            client.request('POST', path, json.dumps(data),
                           headers or {'Content-Type':'application/json'})
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def test_real_calculation_database_and_json_roundtrip(self):
        status, result = self.request({'params':{'forward_w':0}})
        self.assertEqual(status, 200)
        self.assertEqual(result['manual']['bulk_w'], 0)
        self.assertIsNone(result['manual']['bulk_efficiency_pct'])
        raw = json.loads((self.root/'results'/result['run_id']/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(raw, result)
        with closing(sqlite3.connect(self.database)) as con:
            self.assertEqual(con.execute('SELECT source_sha256 FROM rf_runs').fetchone()[0], result['source_sha256'])
            self.assertEqual(con.execute('SELECT COUNT(*) FROM rf_cases').fetchone()[0], 4)

    def test_invalid_input_does_not_create_a_run(self):
        for payload in [{'params':{'cp_pf':0}}, {'params':{'forward_w':float('nan')}},
                        {'params':{'frequency_mhz':True}}, {'unknown':{}}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.request(payload)[0], 400)
        with closing(sqlite3.connect(self.database)) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM rf_runs').fetchone()[0], 0)

    def test_coupled_api_keeps_zero_power_unavailable_and_records_exact_result(self):
        status, result = self.request({'rf_params':{'forward_w':0}}, path='/api/rf/coupled')
        self.assertEqual(status, 200)
        raw = json.loads((self.root/'coupled'/result['run_id']/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(raw, result)
        with closing(sqlite3.connect(self.database)) as con:
            rows = con.execute('SELECT status,density_m3,bulk_w,source_sha256 FROM rf_coupled_cases').fetchall()
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r==('off',None,None,result['source_sha256']) for r in rows))

    def test_wrong_origin_and_content_type_are_rejected(self):
        self.assertEqual(self.request({'params':{}}, {'Content-Type':'application/json','Origin':'https://example.invalid'})[0], 403)
        self.assertEqual(self.request({'params':{}}, {'Content-Type':'text/plain'})[0], 415)


if __name__ == '__main__':
    unittest.main()
