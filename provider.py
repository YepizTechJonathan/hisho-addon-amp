"""AMP (CubeCoders) integration for Hisho (see addon.yaml). Runs inside Core.

Uses AMP's own web API, the one its panel uses: POST /API/Core/Login for a session, then
/API/ADSModule/GetInstances, StartInstance and StopInstance on the controller.
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

#: AMP's application states (AMPType.State). Anything not listed is shown by number.
STATES = {0: "stopped", 5: "pre-start", 10: "starting", 20: "running", 30: "restarting", 40: "stopping",
          45: "preparing to sleep", 50: "sleeping", 60: "waiting", 70: "installing", 75: "updating",
          80: "waiting for input", 100: "failed", 200: "suspended", 250: "maintenance", 999: "unknown"}
_sessions: dict[str, tuple[float, str]] = {}


def panel_url(value: str) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        raise ValueError("no address: give the AMP panel's IP or name")
    if "://" not in text:
        host, _, port = text.partition(":")
        text = f"http://{host}:{port or 8080}"
    return text


def _post(url: str, path: str, body: dict[str, Any], timeout: int = 10) -> Any:
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _session(entry: dict[str, Any], ctx: Any, fresh: bool = False) -> tuple[str, str]:
    url = panel_url(entry["url"])
    key = f"{url}|{entry['user']}"
    hit = _sessions.get(key)
    if hit and not fresh and time.time() - hit[0] < 600:
        return url, hit[1]
    res = _post(url, "/API/Core/Login", {"username": entry["user"], "password": ctx.secret(entry["password"]),
                                         "token": "", "rememberMe": False})
    if not isinstance(res, dict) or not res.get("success") or not res.get("sessionID"):
        reason = (res or {}).get("resultReason") if isinstance(res, dict) else None
        raise PermissionError(f"AMP refused the login{': ' + reason if reason else ''} (check user and password)")
    _sessions[key] = (time.time(), res["sessionID"])
    return url, res["sessionID"]


def _call(entry: dict[str, Any], ctx: Any, path: str, body: dict[str, Any] | None = None) -> Any:
    url, sid = _session(entry, ctx)
    res = _post(url, path, {**(body or {}), "SESSIONID": sid})
    if isinstance(res, dict) and res.get("Title") == "Unauthorized Access":  # session expired
        url, sid = _session(entry, ctx, fresh=True)
        res = _post(url, path, {**(body or {}), "SESSIONID": sid})
    return res


def _instances(entry: dict[str, Any], ctx: Any) -> list[dict[str, Any]]:
    res = _call(entry, ctx, "/API/ADSModule/GetInstances")
    targets = res.get("result", res) if isinstance(res, dict) else res
    out = []
    for target in targets or []:
        for inst in target.get("AvailableInstances") or []:
            if inst.get("Module") == "ADS":  # the controller itself
                continue
            out.append({**inst, "_target": target.get("FriendlyName")})
    return out


def _metric(inst: dict[str, Any], name: str) -> dict[str, Any]:
    return (inst.get("Metrics") or {}).get(name) or {}


def _plain(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return str(exc)
    missing = str(exc).rsplit("missing environment secret:", 1)
    if len(missing) == 2:
        return f"Hisho can't find the secret {missing[1].strip()}; type the password in the form again"
    return f"{type(exc).__name__}: {str(exc)[:160]}"


def summary(entries: dict[str, dict[str, Any]], ctx: Any) -> dict[str, Any]:
    running = total = players = 0
    problems = []
    for name, entry in entries.items():
        try:
            insts = _instances(entry, ctx)
        except Exception as exc:  # noqa: BLE001
            problems.append({"entry": name, "severity": "warn", "title": f"AMP panel {name} does not answer",
                             "detail": f"{panel_url(entry['url'])}: {_plain(exc)}. Is its VM running?"})
            continue
        total += len(insts)
        for i in insts:
            if i.get("Running"):
                running += 1
                players += int(_metric(i, "Active Users").get("RawValue") or 0)
            if STATES.get(i.get("AppState")) == "failed":
                problems.append({"entry": name, "severity": "warn",
                                 "title": f"{i.get('FriendlyName') or i.get('InstanceName')} failed",
                                 "detail": f"The game server on AMP panel {name} is in a failed state."})
    return {"state": "warn" if problems else "ok",
            "headline": f"{running} of {total} servers running · {players} player{'s' * (players != 1)} online",
            "problems": problems}


def details(entries: dict[str, dict[str, Any]], ctx: Any) -> list[dict[str, Any]]:
    sections = []
    for name, entry in entries.items():
        try:
            insts = _instances(entry, ctx)
        except Exception as exc:  # noqa: BLE001
            sections.append({"title": name, "entry": name, "state": "down",
                             "facts": [panel_url(entry["url"]), _plain(exc)], "items": []})
            continue
        items = []
        for i in insts:
            label = i.get("FriendlyName") or i.get("InstanceName")
            state = STATES.get(i.get("AppState"), str(i.get("AppState")))
            facts = [f"{i.get('Module') or 'game'} · {'instance up' if i.get('Running') else 'instance off'} · app {state}"]
            if i.get("Running"):
                users = _metric(i, "Active Users")
                cpu, mem = _metric(i, "CPU Usage"), _metric(i, "Memory Usage")
                if users:
                    facts.append(f"players {users.get('RawValue', 0)} of {users.get('MaxValue', '?')}")
                if cpu:
                    facts.append(f"CPU {cpu.get('Percent', cpu.get('RawValue'))}%")
                if mem:
                    facts.append(f"memory {mem.get('RawValue')} of {mem.get('MaxValue')} MB")
            actions = ([{"id": "stop", "label": "stop", "danger": True,
                         "confirm": f"Stop {label}? Players on it are disconnected."}] if i.get("Running")
                       else [{"id": "start", "label": "start", "confirm": f"Start {label}?"}])
            items.append({"id": i.get("InstanceName"), "name": label,
                          "state": "up" if i.get("Running") and state == "running" else
                                   "warn" if i.get("Running") else "off",
                          "facts": facts, "actions": actions})
        sections.append({"title": name, "entry": name, "state": "ok",
                         "facts": [panel_url(entry["url"]), f"{sum(1 for i in insts if i.get('Running'))} of "
                                                            f"{len(insts)} running"]
                                  + ([entry["note"]] if entry.get("note") else []),
                         "items": items})
    return sections


def test(entry: dict[str, Any], ctx: Any) -> dict[str, Any]:
    try:
        insts = _instances(entry, ctx)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{panel_url(entry.get('url', ''))}: {_plain(exc)}"}
    return {"ok": True, "message": f"Connected: {len(insts)} game server{'s' * (len(insts) != 1)}"}


def act(entries: dict[str, dict[str, Any]], ctx: Any, entry: str, item: str, action: str) -> dict[str, Any]:
    if action not in ("start", "stop"):
        return {"ok": False, "error": f"unknown action {action}"}
    if item not in {i.get("InstanceName") for i in _instances(entries[entry], ctx)}:
        return {"ok": False, "error": f"no game server {item} on {entry}"}
    res = _call(entries[entry], ctx, f"/API/ADSModule/{'StartInstance' if action == 'start' else 'StopInstance'}",
                {"InstanceName": item})
    ok = not (isinstance(res, dict) and (res.get("success") is False or res.get("Status") is False))
    return {"ok": ok, "message": f"{action} sent to {item}",
            "error": None if ok else str((res or {}).get("Reason") or (res or {}).get("resultReason") or res)[:200]}
