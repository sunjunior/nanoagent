"""MCP client for service discovery and tool invocation."""

import json
import urllib.parse
import urllib.request
from typing import Optional


class MCPClient:
    """Discovers MCP services from registry and translates them to OpenAI tools."""

    def __init__(self, registry_url: str = "http://127.0.0.1:5000"):
        self.registry_url = registry_url.rstrip("/")

    def discover_services(self) -> list[dict]:
        url = f"{self.registry_url}/services"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return payload.get("services", [])
        except Exception as exc:
            print(f"Warning: MCP registry unavailable ({exc})")
            return []

    def get_openai_tools(self) -> list[dict]:
        services = self.discover_services()
        tools = []
        for service in services:
            for tool_def in service.get("tools", []):
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_def["name"],
                        "description": tool_def.get("description", ""),
                        "parameters": tool_def.get("parameters", {}),
                    },
                })
        return tools

    def call_service_tool(self, services: list[dict], tool_name: str, args: dict) -> str:
        for service in services:
            for tool_def in service.get("tools", []):
                if tool_def["name"] == tool_name:
                    endpoint = service["endpoint"].rstrip("/")
                    query = urllib.parse.urlencode(args)
                    url = f"{endpoint}/{tool_name}?{query}"
                    request = urllib.request.Request(url, headers={"Accept": "application/json"})
                    try:
                        with urllib.request.urlopen(request, timeout=15) as resp:
                            return resp.read().decode("utf-8")
                    except Exception as exc:
                        return f"Error calling {tool_name}: {exc}"
        return f"Error: tool '{tool_name}' not found in any registered service"
