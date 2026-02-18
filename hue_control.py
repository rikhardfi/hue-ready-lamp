#!/usr/bin/env python3
"""Hue Ready Lamp — Claude Code status indicator via Philips Hue."""

import json
import sys
import time
from pathlib import Path

import requests

CONFIG_PATH = Path.home() / ".hue-claude" / "config.json"
SESSIONS_DIR = Path.home() / ".hue-claude" / "sessions"

# CIE xy color coordinates and brightness for each state
STATES = {
    "thinking": {
        "on": True,
        "xy": [0.1530, 0.0820],  # Blue
        "bri": 254,
        "alert": "lselect",  # Pulsing
    },
    "attention": {
        "on": True,
        "xy": [0.4780, 0.4580],  # Amber/Yellow
        "bri": 254,
        "alert": "lselect",
    },
    "permission": {
        "on": True,
        "xy": [0.5560, 0.4080],  # Orange
        "bri": 254,
        "alert": "lselect",
    },
    "error": {
        "on": True,
        "xy": [0.6750, 0.3220],  # Red
        "bri": 254,
        "alert": "none",
    },
    "success": {
        "on": True,
        "xy": [0.2100, 0.7100],  # Green
        "bri": 254,
        "alert": "none",
    },
    "session": {
        "on": True,
        "xy": [0.3227, 0.3290],  # Dim white
        "bri": 80,
        "alert": "none",
    },
    "off": {
        "on": False,
    },
}

# Priority: higher number wins when multiple sessions are active
STATE_PRIORITY = {
    "off": 0,
    "session": 10,
    "success": 20,
    "thinking": 30,
    "error": 40,
    "attention": 50,
    "permission": 60,
}

# How long to keep the success state before falling back (seconds)
SUCCESS_DURATION = 5

# Sessions older than this are considered stale and cleaned up (seconds)
STALE_THRESHOLD = 3600


def load_config():
    if not CONFIG_PATH.exists():
        print(f"Config not found at {CONFIG_PATH}. Run hue_setup.py first.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def set_light_state(config, state_name):
    if state_name not in STATES:
        print(f"Unknown state: {state_name}", file=sys.stderr)
        print(f"Valid states: {', '.join(STATES.keys())}", file=sys.stderr)
        sys.exit(1)

    bridge_ip = config["bridge_ip"]
    username = config["username"]
    light_id = config["light_id"]
    url = f"http://{bridge_ip}/api/{username}/lights/{light_id}/state"

    state = STATES[state_name]

    try:
        requests.put(url, json=state, timeout=5)
    except requests.RequestException as e:
        print(f"Failed to reach Hue Bridge: {e}", file=sys.stderr)
        sys.exit(1)


def register_session_state(session_id, state_name):
    """Write this session's current state to the registry."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{session_id}.json"
    data = {"state": state_name, "timestamp": time.time()}
    session_file.write_text(json.dumps(data))


def unregister_session(session_id):
    """Remove this session from the registry."""
    session_file = SESSIONS_DIR / f"{session_id}.json"
    try:
        session_file.unlink()
    except FileNotFoundError:
        pass


def cleanup_stale_sessions():
    """Remove session files older than STALE_THRESHOLD."""
    if not SESSIONS_DIR.exists():
        return
    now = time.time()
    for f in SESSIONS_DIR.iterdir():
        if not f.suffix == ".json":
            continue
        try:
            data = json.loads(f.read_text())
            if now - data.get("timestamp", 0) > STALE_THRESHOLD:
                f.unlink()
        except (json.JSONDecodeError, OSError):
            # Corrupted file — remove it
            try:
                f.unlink()
            except OSError:
                pass


def resolve_winning_state():
    """Read all session files and return the highest-priority state, or 'off'."""
    if not SESSIONS_DIR.exists():
        return "off"

    best_state = "off"
    best_priority = STATE_PRIORITY["off"]

    for f in SESSIONS_DIR.iterdir():
        if not f.suffix == ".json":
            continue
        try:
            data = json.loads(f.read_text())
            state = data.get("state", "off")
            priority = STATE_PRIORITY.get(state, 0)
            if priority > best_priority:
                best_priority = priority
                best_state = state
        except (json.JSONDecodeError, OSError):
            continue

    return best_state


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <state> [session_id]", file=sys.stderr)
        print(f"States: {', '.join(STATES.keys())}", file=sys.stderr)
        sys.exit(1)

    state_name = sys.argv[1]
    session_id = sys.argv[2] if len(sys.argv) >= 3 else None

    if state_name not in STATES:
        print(f"Unknown state: {state_name}", file=sys.stderr)
        print(f"Valid states: {', '.join(STATES.keys())}", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    # No session ID — legacy single-session mode
    if session_id is None:
        set_light_state(config, state_name)
        if state_name == "success":
            time.sleep(SUCCESS_DURATION)
            set_light_state(config, "off")
        return

    # Session-aware mode
    cleanup_stale_sessions()

    if state_name == "off":
        # Session ending — unregister and show whatever remains
        unregister_session(session_id)
        winning = resolve_winning_state()
        set_light_state(config, winning)

    elif state_name == "success":
        # Show success, then fall back to "session" (not off)
        register_session_state(session_id, "success")
        winning = resolve_winning_state()
        set_light_state(config, winning)
        time.sleep(SUCCESS_DURATION)
        register_session_state(session_id, "session")
        winning = resolve_winning_state()
        set_light_state(config, winning)

    else:
        # Normal state: register and resolve
        register_session_state(session_id, state_name)
        winning = resolve_winning_state()
        set_light_state(config, winning)


if __name__ == "__main__":
    main()
