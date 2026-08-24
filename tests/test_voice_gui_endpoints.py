"""
Unit Tests for Web GUI Voice Endpoints.
"""

import json
import urllib.request
from ops_assistant.gui.server import start_gui_server
from ops_assistant.agent import OpsAssistantAgent


def test_voice_gui_endpoints():
    agent = OpsAssistantAgent()
    server, url = start_gui_server(host="127.0.0.1", port=0, open_browser=False, agent=agent)
    port = server.server_address[1]

    try:
        # 1. Test GET /api/voice/status
        req_status = urllib.request.Request(f"http://127.0.0.1:{port}/api/voice/status")
        with urllib.request.urlopen(req_status) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert "supported_languages" in data

        # 2. Test POST /api/voice/transcribe (text normalization)
        payload = json.dumps({"text": "sudo apt get update", "language": "en-IN"}).encode("utf-8")
        req_stt = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/voice/transcribe",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_stt) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["text"] == "sudo apt-get update"

    finally:
        server.shutdown()
        server.server_close()
