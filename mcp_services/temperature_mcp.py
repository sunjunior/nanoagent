import json
import os
import socketserver
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 天气 API：http://t.weather.itboy.net/api/weather/city/{9位城市编码}
# 城市编码示例：北京 101010100，深圳 101280601
TEMPERATURE_SOURCE_BASE_URL = os.environ.get(
    "TEMPERATURE_SOURCE_URL",
    "http://t.weather.itboy.net/api/weather/city",
)

HOST = os.environ.get("TEMPERATURE_MCP_HOST", "0.0.0.0")
PUBLISHED_HOST = os.environ.get("TEMPERATURE_MCP_PUBLISHED_HOST", "127.0.0.1")
PORT = int(os.environ.get("TEMPERATURE_MCP_PORT", "8080"))
MCP_REGISTRY_URL = os.environ.get("MCP_REGISTRY_URL", "http://127.0.0.1:5000")

CHUNK_SIZE = 1024


def forward_temperature_request(city_code):
    """向天气 API 发起请求，city_code 为 9 位城市编码。"""
    url = f"{TEMPERATURE_SOURCE_BASE_URL.rstrip('/')}/{city_code}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    return urllib.request.urlopen(request, timeout=15)


def register_service():
    payload = {
        "name": "temperature",
        "endpoint": f"http://{PUBLISHED_HOST}:{PORT}",
        "health": f"http://{PUBLISHED_HOST}:{PORT}/health",
        "description": "Local temperature MCP service",
        "tools": [
            {
                "name": "query_temperature",
                "description": "根据城市编码查询天气和温度",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city_code": {
                            "type": "string",
                            "description": "9 位中国城市行政区划代码，例如北京 101010100、上海 101020100、深圳 101280601、广州 101280101"
                        }
                    },
                    "required": ["city_code"]
                }
            }
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    url = f"{MCP_REGISTRY_URL.rstrip('/')}/register"
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            response_body = resp.read().decode("utf-8")
            print(f"Registered temperature service with registry: {response_body}")
    except Exception as exc:
        print(f"Failed to register temperature service with MCP registry: {exc}")


class TemperatureHandler(BaseHTTPRequestHandler):
    def _send_chunk(self, chunk_data: bytes):
        if not chunk_data:
            return
        chunk_size = f"{len(chunk_data):X}\r\n".encode("utf-8")
        self.wfile.write(chunk_size)
        self.wfile.write(chunk_data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _end_chunks(self):
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _parse_city_code(self):
        if self.command == "GET":
            parsed = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed.query)
            return query_params.get("city_code", [None])[0]

        if self.command == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(body.decode("utf-8"))
                return payload.get("city_code")
            except Exception:
                return None

        return None

    def _write_json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._write_json_response(200, {"status": "ok"})
            return

        if self.path.startswith("/temperature"):
            city_code = self._parse_city_code()
            if not city_code:
                self._write_json_response(400, {"error": "city_code parameter required (9-digit code)"})
                return

            try:
                with forward_temperature_request(city_code) as resp:
                    self.send_response(200)
                    self.send_header("Content-Type", resp.headers.get_content_type() or "application/json")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()

                    while True:
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        self._send_chunk(chunk)
                    self._end_chunks()
            except urllib.error.HTTPError as exc:
                self._write_json_response(exc.code, {"error": exc.reason})
            except Exception as exc:
                self._write_json_response(500, {"error": str(exc)})
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path.startswith("/temperature"):
            self.do_GET()
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # 使用更简洁的日志输出
        print(f"[temperature_mcp] {self.address_string()} - {format % args}")


def main():
    server_address = (HOST, PORT)
    register_service()
    with ThreadingHTTPServer(server_address, TemperatureHandler) as httpd:
        print(f"Temperature MCP service running at http://{HOST}:{PORT}")
        print(f"Forwarding temperature queries to {TEMPERATURE_SOURCE_BASE_URL}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Temperature MCP service stopped.")


if __name__ == "__main__":
    main()
