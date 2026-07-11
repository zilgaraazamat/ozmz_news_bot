"""Общие низкоуровневые хелперы ответа HTTP — используются всеми остальными
route-миксинами через общий Handler (см. server.py)."""
import os
import json

# server.py живёт в корне проекта, а этот файл — на один уровень глубже
# (routes/base.py), поэтому поднимаемся на директорию выше, чтобы
# относительные пути вида "webapp/app.html" резолвились так же, как раньше.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseRoutesMixin:
    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, rel_path, content_type):
        full = os.path.join(_PROJECT_ROOT, rel_path)
        try:
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if content_type.startswith("text/html"):
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            else:
                self.send_header("Cache-Control", "public, max-age=86400")

            if content_type.startswith("text/") and "gzip" in self.headers.get("Accept-Encoding", ""):
                import gzip
                data = gzip.compress(data, compresslevel=6)
                self.send_header("Content-Encoding", "gzip")

            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()
