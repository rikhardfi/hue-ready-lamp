# Hue Ready Lamp

A physical status indicator for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) using a Philips Hue smart bulb. See at a glance what Claude is doing — without looking at your screen.

## Quick Start

```bash
bash install.sh
```

The installer will:
1. Check for Python 3
2. Install dependencies (`requests`)
3. Run the setup wizard (discover bridge, authenticate, pick a light)
4. Configure Claude Code hooks in `~/.claude/settings.json`

## Lamp States

| State | Color | Behavior | Duration | Meaning |
|---|---|---|---|---|
| **Thinking** | Blue | Pulsing | ~15 seconds* | Claude is processing your prompt |
| **Attention** | Amber | Pulsing | ~15 seconds* | Claude is idle — waiting for your input |
| **Permission** | Orange | Pulsing | ~15 seconds* | Claude needs your approval to proceed |
| **Error** | Red | Solid | Until next state change | A tool or operation failed |
| **Success** | Green | Solid | 5 seconds, then dim white | Claude finished the response |
| **Session** | Dim white | Solid | Until session ends | A Claude Code session is active |
| **Off** | - | - | - | No active session |

*\*The Hue `lselect` alert mode pulses for approximately 15 seconds, then stops. The light stays on at the set color but stops pulsing. It is not an infinite blink — if Claude thinks longer than ~15s the lamp will remain solid blue/amber/orange.*

### Visual Flow

```
Session starts     -->  Dim white (solid)
You send a prompt  -->  Blue (pulsing ~15s)
Claude responds    -->  Green (5s) --> Dim white
Claude needs input -->  Amber (pulsing ~15s)
Claude needs perms -->  Orange (pulsing ~15s)
A tool fails       -->  Red (solid)
Session ends       -->  Off (or previous session's state)
```

## Manual Control

```bash
python3 hue_control.py thinking     # Blue pulsing
python3 hue_control.py attention    # Amber pulsing
python3 hue_control.py permission   # Orange pulsing
python3 hue_control.py error        # Red solid
python3 hue_control.py success      # Green 5s, then dim white
python3 hue_control.py session      # Dim white
python3 hue_control.py off          # Turn off
```

## Concurrent Sessions

Multiple Claude Code sessions can share the same lamp. Each session registers its state in `~/.hue-claude/sessions/`, and the lamp always shows the highest-priority state across all active sessions:

1. **Permission** (orange) > **Attention** (amber) > **Error** (red) > **Thinking** (blue) > **Success** (green) > **Session** (dim white) > **Off**
2. When a session ends, the lamp falls back to the next active session's state instead of turning off
3. Success now transitions to "session" (dim white) instead of off, since the session is still alive
4. Stale session files (from crashed sessions) are automatically cleaned up after 1 hour

The installer passes `$PPID` (the Claude Code process PID) as a session identifier. Legacy usage without a session ID still works in single-session mode.

## Known Limitations

### Pulse duration is fixed by the Hue bridge

The `lselect` pulsing mode runs for ~15 seconds and cannot be extended via the API. For long-running operations, the light stays on but stops pulsing after ~15s.

## Files

| File | Purpose |
|---|---|
| `hue_control.py` | Main lamp controller — sets light states via Hue API |
| `hue_setup.py` | One-time setup wizard (bridge discovery, auth, light selection) |
| `install.sh` | Full installer (deps + setup + Claude Code hooks) |
| `requirements.txt` | Python dependencies |

## Configuration

Config is stored at `~/.hue-claude/config.json`:

```json
{
  "bridge_ip": "192.168.x.x",
  "username": "<hue-api-username>",
  "light_id": "2",
  "light_name": "Desk Lamp"
}
```

Claude Code hooks are written to `~/.claude/settings.json` under the `hooks` key. All hooks run asynchronously so they never block Claude's responses.

## Requirements

- Python 3
- Philips Hue Bridge + at least one color-capable Hue light
- Claude Code
