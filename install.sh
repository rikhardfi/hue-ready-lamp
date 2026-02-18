#!/bin/bash
# Hue Ready Lamp — Installer
# Sets up Python dependencies, runs Hue setup, and configures Claude Code hooks.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTROL_SCRIPT="$SCRIPT_DIR/hue_control.py"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "=================================================="
echo "  Hue Ready Lamp — Installer"
echo "=================================================="
echo

# Step 1: Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is required but not found."
    exit 1
fi
echo "Found Python 3: $(python3 --version)"

# Step 2: Install requests
echo
echo "Installing Python dependencies..."
python3 -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "Dependencies installed."

# Step 3: Run setup wizard
echo
python3 "$SCRIPT_DIR/hue_setup.py"

# Step 4: Configure Claude Code hooks
echo
echo "Configuring Claude Code hooks..."

# Escape the path for use in shell commands within JSON
# Use the raw path — Python handles it fine
ESCAPED_PATH="$CONTROL_SCRIPT"

python3 -c "
import json
from pathlib import Path

settings_path = Path('$SETTINGS_FILE')
control_script = '''$ESCAPED_PATH'''

# Build the hooks config
def make_hook(state):
    return {
        'hooks': [{
            'type': 'command',
            'command': f'python3 \"{control_script}\" {state} \$PPID',
            'async': True,
        }]
    }

def make_notification_hook(matcher, state):
    hook = make_hook(state)
    hook['matcher'] = matcher
    return hook

new_hooks = {
    'UserPromptSubmit': [make_hook('thinking')],
    'Notification': [
        make_notification_hook('idle_prompt', 'attention'),
        make_notification_hook('permission_prompt', 'permission'),
    ],
    'PostToolUseFailure': [make_hook('error')],
    'Stop': [make_hook('success')],
    'SessionStart': [make_hook('session')],
    'SessionEnd': [make_hook('off')],
}

# Load existing settings or start fresh
if settings_path.exists():
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = {}

# Merge hooks — replace only our hook events, preserve others
existing_hooks = settings.get('hooks', {})
existing_hooks.update(new_hooks)
settings['hooks'] = existing_hooks

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print(f'Hooks written to {settings_path}')
"

echo
echo "=================================================="
echo "  Setup complete!"
echo "=================================================="
echo
echo "Test it:"
echo "  python3 \"$CONTROL_SCRIPT\" thinking   # Blue pulsing"
echo "  python3 \"$CONTROL_SCRIPT\" attention   # Amber pulsing"
echo "  python3 \"$CONTROL_SCRIPT\" success     # Green (5s then off)"
echo "  python3 \"$CONTROL_SCRIPT\" off         # Turn off"
echo
echo "The lamp will now respond to Claude Code automatically."
echo "Start a new Claude Code session to try it out!"
