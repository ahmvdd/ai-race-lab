"""Serveur local minimal pour diffuser une partie en direct au navigateur.

Aucune dépendance ajoutée : http.server (stdlib) + Server-Sent Events.
Un seul process, usage local uniquement (127.0.0.1).
"""

from __future__ import annotations

import json
import queue
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

VIEWER_DIR = Path(__file__).resolve().parent.parent / "viewer"
VIEWER_HTML = VIEWER_DIR / "live.html"
STATIC_FILES = {
    "/style.css": (VIEWER_DIR / "style.css", "text/css; charset=utf-8"),
}


class _FastBindHTTPServer(ThreadingHTTPServer):
    """Évite l'appel à socket.getfqdn() de HTTPServer.server_bind(), qui peut bloquer
    plusieurs dizaines de secondes selon la config DNS locale — inutile pour un usage 127.0.0.1."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


def start_server(handler_class, host: str, port: int) -> _FastBindHTTPServer:
    """Démarre un serveur dans un thread daemon, en essayant quelques ports si occupé."""
    httpd: Optional[_FastBindHTTPServer] = None
    last_error: Optional[OSError] = None
    for candidate_port in range(port, port + 10):
        try:
            httpd = _FastBindHTTPServer((host, candidate_port), handler_class)
            break
        except OSError as exc:
            last_error = exc
    if httpd is None:
        raise last_error or OSError("Impossible de démarrer le serveur local")
    httpd.daemon_threads = True  # les connexions ouvertes ne doivent jamais bloquer l'arrêt

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


class LiveServer:
    """Diffuse des événements JSON à tous les navigateurs connectés (SSE sur /events)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._clients: List["queue.Queue[str]"] = []
        self._lock = threading.Lock()
        self._httpd: Optional[_FastBindHTTPServer] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def broadcast(self, event: Dict) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        with self._lock:
            clients = list(self._clients)
        for client_queue in clients:
            client_queue.put(payload)

    def start(self) -> None:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # silence les logs HTTP par défaut
                pass

            def do_GET(self) -> None:  # noqa: N802 (nom imposé par BaseHTTPRequestHandler)
                if self.path == "/events":
                    self._serve_events()
                elif self.path in STATIC_FILES:
                    self._serve_static(self.path)
                else:
                    self._serve_page()

            def _serve_events(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                client_queue: "queue.Queue[str]" = queue.Queue()
                with server._lock:
                    server._clients.append(client_queue)
                try:
                    while True:
                        try:
                            payload = client_queue.get(timeout=15)
                            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        except queue.Empty:
                            self.wfile.write(b": keep-alive\n\n")  # détecte les clients partis
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    with server._lock:
                        if client_queue in server._clients:
                            server._clients.remove(client_queue)

            def _serve_page(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(VIEWER_HTML.read_bytes())

            def _serve_static(self, path: str) -> None:
                file_path, content_type = STATIC_FILES[path]
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(file_path.read_bytes())

        self._httpd = start_server(Handler, self.host, self.port)
        self.port = self._httpd.server_address[1]

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
