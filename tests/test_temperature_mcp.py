import http.client
import io
import json
import os
import sys
import threading
import urllib.error
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import mcp_services.temperature_mcp as temperature_mcp


class DummyHeaders:
    def __init__(self, content_type="application/json"):
        self._content_type = content_type

    def get_content_type(self):
        return self._content_type


class DummyResponse:
    def __init__(self, chunks, content_type="application/json"):
        self._chunks = iter(chunks)
        self.headers = DummyHeaders(content_type)

    def read(self, size=-1):
        return next(self._chunks, b"")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestTemperatureMCP(unittest.TestCase):
    def test_register_service_success(self):
        dummy = DummyResponse([b"{\"status\": \"registered\"}"])

        with patch("mcp_services.temperature_mcp.urllib.request.urlopen", return_value=dummy) as mocked:
            temperature_mcp.register_service()
            mocked.assert_called_once()

    def test_register_service_failure(self):
        with patch("mcp_services.temperature_mcp.urllib.request.urlopen", side_effect=urllib.error.URLError("fail")) as mocked:
            temperature_mcp.register_service()
            mocked.assert_called_once()

    def test_temperature_endpoint_returns_body(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), temperature_mcp.TemperatureHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)

        def source_urlopen(request, timeout=15):
            return DummyResponse([b'{"temp": 20}'])

        with patch("mcp_services.temperature_mcp.urllib.request.urlopen", side_effect=source_urlopen):
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port)
                conn.request("GET", "/temperature?city_code=101010100")
                resp = conn.getresponse()
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.read().decode("utf-8"), '{"temp": 20}')
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1)

    def test_temperature_endpoint_missing_city(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), temperature_mcp.TemperatureHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)

        with patch("mcp_services.temperature_mcp.urllib.request.urlopen", side_effect=Exception("should not be called")):
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port)
                conn.request("GET", "/temperature")
                resp = conn.getresponse()
                self.assertEqual(resp.status, 400)
                body = json.loads(resp.read().decode("utf-8"))
                self.assertIn("city_code", body["error"])
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1)
