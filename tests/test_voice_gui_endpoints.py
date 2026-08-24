"""
Unit Tests for Web GUI Voice Endpoints.
"""

import json
import urllib.request
from ops_assistant.gui.server import start_gui_server
from ops_assistant.agent import OpsAssistantAgent


def test_voice_gui_endpoints():
    import threading
    import time
    agent = OpsAssistantAgent()
    server, url = start_gui_server(host="127.0.0.1", port=9933, open_browser=False, agent=agent)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)

    try:
        # 1. Test GET /api/voice/status
        req_status = urllib.request.Request(f"{url}/api/voice/status", headers={"Connection": "close"})
        with urllib.request.urlopen(req_status, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert "supported_languages" in data

        # 2. Test POST /api/voice/transcribe (text normalization)
        payload = json.dumps({"text": "sudo apt get update", "language": "en-IN"}).encode("utf-8")
        req_stt = urllib.request.Request(
            f"{url}/api/voice/transcribe",
            data=payload,
            headers={"Content-Type": "application/json", "Connection": "close"}
        )
        with urllib.request.urlopen(req_stt, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["text"] == "sudo apt-get update"

    finally:
        server.shutdown()
        server.server_close()
