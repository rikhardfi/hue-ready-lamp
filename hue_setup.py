#!/usr/bin/env python3
"""Hue Ready Lamp — One-time setup wizard for Philips Hue integration."""

import json
import sys
import time
from pathlib import Path

import requests

CONFIG_DIR = Path.home() / ".hue-claude"
CONFIG_PATH = CONFIG_DIR / "config.json"


def discover_bridge():
    """Find Hue Bridge on the network via Philips discovery API."""
    print("Searching for Hue Bridge on your network...")
    try:
        resp = requests.get("https://discovery.meethue.com/", timeout=10)
        bridges = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Discovery failed: {e}")
        return None

    if not bridges:
        print("No Hue Bridge found via cloud discovery.")
        return None

    if len(bridges) == 1:
        ip = bridges[0]["internalipaddress"]
        print(f"Found Hue Bridge at {ip}")
        return ip

    print("Multiple bridges found:")
    for i, b in enumerate(bridges, 1):
        print(f"  {i}. {b['internalipaddress']} (id: {b.get('id', 'unknown')})")
    while True:
        choice = input(f"Pick a bridge [1-{len(bridges)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(bridges):
            return bridges[int(choice) - 1]["internalipaddress"]
        print("Invalid choice, try again.")


def create_username(bridge_ip):
    """Create an API username by having user press the bridge button."""
    url = f"http://{bridge_ip}/api"
    body = {"devicetype": "hue_claude_lamp#claude_code"}

    print()
    print(">>> Press the button on your Hue Bridge, then press Enter here. <<<")
    input()

    # Try a few times in case the button press timing is tight
    for attempt in range(5):
        try:
            resp = requests.post(url, json=body, timeout=5)
            result = resp.json()
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            time.sleep(2)
            continue

        if isinstance(result, list) and result:
            entry = result[0]
            if "success" in entry:
                username = entry["success"]["username"]
                print(f"Authenticated successfully.")
                return username
            if "error" in entry:
                error = entry["error"]
                if error.get("type") == 101:
                    print(f"Bridge button not pressed yet. Retrying ({attempt + 1}/5)...")
                    time.sleep(3)
                    continue
                print(f"Bridge error: {error.get('description', error)}")
                return None

    print("Could not authenticate. Make sure you press the bridge button first.")
    return None


def list_lights(bridge_ip, username):
    """Fetch all lights from the bridge."""
    url = f"http://{bridge_ip}/api/{username}/lights"
    try:
        resp = requests.get(url, timeout=5)
        return resp.json()
    except requests.RequestException as e:
        print(f"Failed to get lights: {e}")
        return {}


def pick_light(lights):
    """Let user pick a light from the list."""
    if not lights:
        print("No lights found on the bridge!")
        return None, None

    print()
    print("Available lights:")
    sorted_ids = sorted(lights.keys(), key=int)
    for light_id in sorted_ids:
        light = lights[light_id]
        name = light.get("name", "Unknown")
        model = light.get("modelid", "")
        reachable = light.get("state", {}).get("reachable", False)
        status = "reachable" if reachable else "unreachable"
        print(f"  {light_id}. {name} ({model}) [{status}]")

    print()
    while True:
        choice = input(f"Pick a light by number [{sorted_ids[0]}-{sorted_ids[-1]}]: ").strip()
        if choice in lights:
            return choice, lights[choice].get("name", "Light " + choice)
        print("Invalid choice, try again.")


def test_light(bridge_ip, username, light_id):
    """Flash the selected light green to confirm it works."""
    url = f"http://{bridge_ip}/api/{username}/lights/{light_id}/state"
    # Flash green
    requests.put(url, json={"on": True, "xy": [0.21, 0.71], "bri": 254, "alert": "select"}, timeout=5)
    time.sleep(2)
    # Return to previous state
    requests.put(url, json={"alert": "none"}, timeout=5)


def save_config(bridge_ip, username, light_id, light_name):
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {
        "bridge_ip": bridge_ip,
        "username": username,
        "light_id": light_id,
        "light_name": light_name,
    }
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Config saved to {CONFIG_PATH}")
    return config


def main():
    print("=" * 50)
    print("  Hue Ready Lamp — Setup Wizard")
    print("=" * 50)
    print()

    # Step 1: Discover bridge
    bridge_ip = discover_bridge()
    if not bridge_ip:
        manual = input("Enter bridge IP manually (or press Enter to quit): ").strip()
        if not manual:
            sys.exit(1)
        bridge_ip = manual

    # Step 2: Authenticate
    username = create_username(bridge_ip)
    if not username:
        sys.exit(1)

    # Step 3: Pick a light
    lights = list_lights(bridge_ip, username)
    light_id, light_name = pick_light(lights)
    if not light_id:
        sys.exit(1)

    # Step 4: Test it
    print(f"\nTesting '{light_name}'... (should flash green)")
    test_light(bridge_ip, username, light_id)

    # Step 5: Save config
    print()
    save_config(bridge_ip, username, light_id, light_name)

    print()
    print("Setup complete! You can now test with:")
    print(f"  python3 hue_control.py thinking")
    print(f"  python3 hue_control.py off")


if __name__ == "__main__":
    main()
