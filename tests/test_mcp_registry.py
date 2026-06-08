import json
import threading
import urllib.request
import urllib.error
import os
import sys
import unittest
from http.server import ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import mcp_registry


class TestMCPRegistry(unittest.TestCase):
    def setUp(self):
        mcp_registry.registered_services.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), mcp_registry.MCPRegistryHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_health_endpoint(self):
        with urllib.request.urlopen(self._url("/health")) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(json.loads(resp.read().decode("utf-8")), {"status": "ok"})

    def test_register_and_services(self):
        payload = {
            "name": "temperature",
            "endpoint": "http://127.0.0.1:8080/temperature",
            "health": "http://127.0.0.1:8080/health",
            "description": "温度服务",
            "tools": [
                {
                    "name": "query_temperature",
                    "description": "查询温度",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                }
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._url("/register"),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body["status"], "registered")
            self.assertEqual(body["service"]["name"], "temperature")

        with urllib.request.urlopen(self._url("/services")) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(body["services"][0]["tools"]), 1)
            self.assertEqual(body["services"][0]["tools"][0]["name"], "query_temperature")

    def test_register_invalid_payload(self):
        request = urllib.request.Request(
            self._url("/register"),
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(request)

        self.assertEqual(cm.exception.code, 400)

    def test_not_found_path(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(self._url("/unknown"))

        self.assertEqual(cm.exception.code, 404)
