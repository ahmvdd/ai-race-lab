"""Tests du serveur local de diffusion live — pas d'Ollama, pas de navigateur."""

import json
import urllib.request

from ai_race.live_server import LiveServer


def test_server_starts_and_serves_page():
    server = LiveServer(port=8901)
    server.start()
    try:
        with urllib.request.urlopen(server.url, timeout=2) as resp:
            body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "AI Race Lab" in body
    finally:
        server.stop()


def test_broadcast_reaches_connected_client():
    server = LiveServer(port=8902)
    server.start()
    try:
        conn = urllib.request.urlopen(server.url + "events", timeout=2)
        server.broadcast({"type": "move", "agent": "A"})
        line = conn.readline().decode("utf-8").strip()
        assert line.startswith("data: ")
        payload = json.loads(line[len("data: "):])
        assert payload == {"type": "move", "agent": "A"}
        conn.close()
    finally:
        server.stop()


def test_broadcast_without_clients_does_not_raise():
    server = LiveServer(port=8903)
    server.start()
    try:
        server.broadcast({"type": "episode_start"})
    finally:
        server.stop()
