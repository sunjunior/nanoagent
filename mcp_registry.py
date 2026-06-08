import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MCP_REGISTRY_HOST = os.environ.get("MCP_REGISTRY_HOST", "0.0.0.0")
MCP_REGISTRY_PORT = int(os.environ.get("MCP_REGISTRY_PORT", "5000"))

registered_services = []


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class MCPRegistryHandler(BaseHTTPRequestHandler):
    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b""
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None

    def do_GET(self):
        if self.path.startswith("/health"):
            send_json(self, 200, {"status": "ok"})
            return

        if self.path.startswith("/services"):
            send_json(self, 200, {"services": registered_services})
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path.startswith("/register"):
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                send_json(self, 400, {"error": "Invalid JSON payload"})
                return

            for field in ("name", "endpoint", "health"):
                if not payload.get(field) or not isinstance(payload[field], str):
                    send_json(self, 400, {"error": f"{field} is required and must be a string"})
                    return

            service = {
                "name": payload["name"].strip(),
                "endpoint": payload["endpoint"].strip(),
                "health": payload["health"].strip(),
                "description": payload.get("description", "").strip(),
                "tools": payload.get("tools", []),
            }

            for idx, existing in enumerate(registered_services):
                if existing.get("name") == service["name"] and existing.get("endpoint") == service["endpoint"]:
                    registered_services[idx] = service
                    break
            else:
                registered_services.append(service)

            send_json(self, 200, {"status": "registered", "service": service})
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        print(f"[mcp_registry] {self.address_string()} - {format % args}")


def main():
    server_address = (MCP_REGISTRY_HOST, MCP_REGISTRY_PORT)
    with ThreadingHTTPServer(server_address, MCPRegistryHandler) as httpd:
        print(f"MCP registry service running at http://{MCP_REGISTRY_HOST}:{MCP_REGISTRY_PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("MCP registry service stopped.")


if __name__ == "__main__":
    main()
