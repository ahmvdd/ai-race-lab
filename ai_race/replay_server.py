"""Serveur local minimal pour rejouer une session dans le navigateur sans glisser de fichier.

Sert viewer/index.html + le session_*.jsonl choisi sur /session.jsonl : la page le
récupère automatiquement au chargement (voir le fetch() en tête de viewer/index.html).
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

from .live_server import STATIC_FILES, VIEWER_DIR, _FastBindHTTPServer, start_server

INDEX_HTML = VIEWER_DIR / "index.html"


class ReplayServer:
    """Sert la page de replay pré-chargée avec un fichier session_*.jsonl donné."""

    def __init__(self, session_path: Path, host: str = "127.0.0.1", port: int = 8766):
        self.session_path = Path(session_path)
        self.host = host
        self.port = port
        self._httpd: Optional[_FastBindHTTPServer] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def start(self) -> None:
        session_path = self.session_path

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # silence les logs HTTP par défaut
                pass

            def do_GET(self) -> None:  # noqa: N802 (nom imposé par BaseHTTPRequestHandler)
                if self.path == "/session.jsonl":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(session_path.read_bytes())
                elif self.path in STATIC_FILES:
                    file_path, content_type = STATIC_FILES[self.path]
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.end_headers()
                    self.wfile.write(file_path.read_bytes())
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(INDEX_HTML.read_bytes())

        self._httpd = start_server(Handler, self.host, self.port)
        self.port = self._httpd.server_address[1]

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
