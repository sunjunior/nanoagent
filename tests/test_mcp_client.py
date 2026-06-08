import json
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from mcp_client import MCPClient


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data
    def read(self, size=-1):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


MOCK_SERVICES = [
    {
        "name": "temperature",
        "endpoint": "http://127.0.0.1:8080",
        "health": "http://127.0.0.1:8080/health",
        "description": "温度服务",
        "tools": [
            {
                "name": "query_temperature",
                "description": "查询温度",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "城市"}},
                    "required": ["city"],
                },
            }
        ],
    }
]


class TestMCPClient(unittest.TestCase):
    def setUp(self):
        self.client = MCPClient("http://127.0.0.1:5000")

    def test_discover_services(self):
        dummy = DummyResponse(json.dumps({"services": MOCK_SERVICES}).encode("utf-8"))
        with patch("mcp_client.urllib.request.urlopen", return_value=dummy):
            services = self.client.discover_services()
            self.assertEqual(len(services), 1)
            self.assertEqual(services[0]["name"], "temperature")

    def test_discover_services_unavailable(self):
        with patch("mcp_client.urllib.request.urlopen", side_effect=Exception("refused")):
            services = self.client.discover_services()
            self.assertEqual(services, [])

    def test_get_openai_tools(self):
        dummy = DummyResponse(json.dumps({"services": MOCK_SERVICES}).encode("utf-8"))
        with patch("mcp_client.urllib.request.urlopen", return_value=dummy):
            tools = self.client.get_openai_tools()
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["type"], "function")
            self.assertEqual(tools[0]["function"]["name"], "query_temperature")

    def test_call_service_tool_found(self):
        dummy = DummyResponse(b'{"temp": 25}')
        with patch("mcp_client.urllib.request.urlopen", return_value=dummy) as mocked:
            result = self.client.call_service_tool(MOCK_SERVICES, "query_temperature", {"city": "Beijing"})
            self.assertEqual(result, '{"temp": 25}')
            called_url = mocked.call_args[0][0].full_url
            self.assertIn("Beijing", called_url)

    def test_call_service_tool_not_found(self):
        result = self.client.call_service_tool(MOCK_SERVICES, "nonexistent", {})
        self.assertIn("not found", result)

    def test_call_service_tool_http_error(self):
        with patch("mcp_client.urllib.request.urlopen", side_effect=Exception("timeout")):
            result = self.client.call_service_tool(MOCK_SERVICES, "query_temperature", {"city": "Beijing"})
            self.assertIn("Error calling", result)

    def test_get_openai_tools_empty_when_no_services(self):
        dummy = DummyResponse(json.dumps({"services": []}).encode("utf-8"))
        with patch("mcp_client.urllib.request.urlopen", return_value=dummy):
            tools = self.client.get_openai_tools()
            self.assertEqual(tools, [])
