"""API integration checks, separate from physical model validation."""
from __future__ import annotations

import json
import socket
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim_app.server import Handler, ThreadingHTTPServer, schema, simulate_request, sweep_request


class ServerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def test_http_schema_and_health(self):
        self.assertEqual(self.request("/api/health")["status"], "ok")
        result = self.request("/api/schema")
        self.assertEqual(set(result["models"]), {"ald", "etch"})
        for model in result["models"].values():
            self.assertGreater(len(model["params"]), 5)
            self.assertEqual(len({p["key"] for p in model["params"]}), len(model["params"]))
            self.assertIn("none", {fault["id"] for fault in model["faults"]})

    def test_request_identity_reproducible_and_model_sensitive(self):
        first = self.request("/api/simulate", {"model": "etch"})
        second = simulate_request({"model": "etch"})
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["result"], second["result"])
        self.assertIsNone(first["baseline"])
        ald = simulate_request({"model": "ald"})
        self.assertNotEqual(first["run_id"], ald["run_id"])

    def test_fault_baseline_uses_same_recipe_without_fault(self):
        spec = schema()["models"]["etch"]
        fault = next(item["id"] for item in spec["faults"] if item["id"] != "none")
        faulty = simulate_request({"model": "etch", "fault": fault})
        healthy = simulate_request({"model": "etch", "params": faulty["params"]})
        self.assertEqual(faulty["baseline"], healthy["result"])
        self.assertNotEqual(faulty["run_id"], healthy["run_id"])

    def test_integer_and_float_recipe_values_have_same_identity(self):
        integer = simulate_request({"model": "etch", "params": {"source_power_w": 600}})
        floating = simulate_request({"model": "etch", "params": {"source_power_w": 600.0}})
        self.assertEqual(integer["run_id"], floating["run_id"])

    def test_sweep_reproduces_individual_endpoint_samples(self):
        item = next(p for p in schema()["models"]["etch"]["params"] if p["key"] == "fault_severity")
        values = [item["min"], item["default"], item["max"]]
        request = {"model": "etch", "parameter": "fault_severity", "values": values}
        result = sweep_request(request)
        for value, row in zip(values, result["runs"]):
            individual = simulate_request({"model": "etch", "params": {"fault_severity": value}})
            self.assertEqual(row["metrics"], individual["result"]["metrics"])

    def test_invalid_requests_return_400(self):
        invalid = [
            [], {"model": "unknown"}, {"model": "etch", "extra": 1},
            {"model": "etch", "params": {"hidden_density": 1e99}},
            {"model": "etch", "params": {"fault_severity": float("nan")}},
            {"model": "etch", "params": {"fault_severity": True}},
            {"model": "etch", "params": {"fault_severity": 1.01}},
            {"model": "etch", "params": {"source_power_w": 10 ** 400}},
            {"model": "etch", "fault": "invented_fault"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(HTTPError) as context:
                    self.request("/api/simulate", payload)
                self.assertEqual(context.exception.code, 400)
                self.assertIn("error", json.load(context.exception))

    def test_sweep_rejects_oversized_or_nonfinite_input(self):
        for values in ([0], [0] * 22, [0, float("inf")]):
            with self.assertRaises(ValueError):
                sweep_request({"model": "etch", "parameter": "fault_severity", "values": values})

    def test_static_traversal_is_not_served(self):
        with self.assertRaises(HTTPError) as context:
            self.request("/%2e%2e/server.py")
        self.assertEqual(context.exception.code, 403)

    def test_incomplete_clients_do_not_occupy_computation_slots(self):
        sockets = []
        try:
            for _ in range(2):
                connection = socket.create_connection(self.server.server_address, timeout=2)
                connection.sendall(b"POST /api/simulate HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\n")
                sockets.append(connection)
            result = self.request("/api/simulate", {"model": "etch"})
            self.assertEqual(result["model"], "etch")
        finally:
            for connection in sockets:
                connection.close()


if __name__ == "__main__":
    unittest.main()
