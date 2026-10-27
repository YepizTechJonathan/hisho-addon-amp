"""AMP add-on tests. Run with Hisho's venv at the repository's top:
~/code/hisho/.venv/bin/python -m pytest -q"""
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from hisho import addon_store, addons
from hisho.addon_testing import AUTH, TOKEN, Recorder

HERE = Path(__file__).resolve().parents[1]


def ctx_for(addon):
    return addons.Context(addon, resolve=lambda name: f"value-of-{name}")


def test_manifest_is_valid_and_readme_matches(addon):
    assert addons.validate_manifest(addon.manifest) == []
    assert addon_store.readme_problems(HERE) == []


def test_the_amp_integration_lists_instances_logs_in_once_and_starts_one(fleet, monkeypatch):
    import io, json as _json
    amp = addons.get("amp")
    addons.set_entry(amp, "games", {"url": "198.51.100.30", "user": "admin", "password": "HISHO_AMP_PW"})
    calls = []
    instances = [{"FriendlyName": "Controller", "AvailableInstances": [
        {"InstanceName": "ADS01", "Module": "ADS", "Running": True, "AppState": 20},
        {"InstanceName": "Minecraft01", "FriendlyName": "Minecraft", "Module": "Minecraft", "Running": True,
         "AppState": 20, "Metrics": {"Active Users": {"RawValue": 3, "MaxValue": 20},
                                     "CPU Usage": {"RawValue": 12, "Percent": 12},
                                     "Memory Usage": {"RawValue": 2048, "MaxValue": 8192}}},
        {"InstanceName": "Valheim01", "FriendlyName": "Valheim", "Module": "GenericModule", "Running": False,
         "AppState": 0}]}]

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def urlopen(req, timeout=0):
        body = _json.loads(req.data)
        calls.append((req.full_url, body))
        if req.full_url.endswith("/API/Core/Login"):
            assert body["password"] == "pw" and req.full_url.startswith("http://198.51.100.30:8080/")
            return Resp(_json.dumps({"success": True, "sessionID": "sid1"}).encode())
        assert body["SESSIONID"] == "sid1"
        if req.full_url.endswith("GetInstances"):
            return Resp(_json.dumps({"result": instances}).encode())
        return Resp(_json.dumps({"success": True}).encode())
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    ctx = addons.Context(amp, resolve=lambda name: "pw")
    from importlib import util
    spec = util.spec_from_file_location("amp_provider", HERE / "provider.py")
    addons.provider(amp)._sessions.clear()
    assert addons.summarize(amp, ctx)["headline"] == "1 of 2 servers running · 3 players online"
    [sec] = addons.details(amp, ctx)
    mc, vh = sec["items"]
    assert mc["facts"][1] == "players 3 of 20" and mc["actions"][0]["id"] == "stop"
    assert vh["actions"][0]["id"] == "start"
    assert addons.act(amp, "games", "Valheim01", "start", ctx)["ok"]
    assert calls[-1][0].endswith("/API/ADSModule/StartInstance") and calls[-1][1]["InstanceName"] == "Valheim01"
    assert sum(1 for c in calls if c[0].endswith("/Login")) == 1  # one session reused
    assert addons.act(amp, "games", "Nope", "start", ctx)["ok"] is False
