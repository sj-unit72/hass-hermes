# Hermes Conversation for Home Assistant

A custom Home Assistant integration that registers [Hermes Agent](https://github.com/NousResearch/hermes-agent) as a conversation agent. Drop it into your existing Voice Assistant pipeline (Voice PE, mobile app, chat panel) and Hermes provides the brains while HA keeps doing STT and TTS.

## What you get

- "Okay Nabu, turn off the downstairs lights" → handled by Hermes via its built-in HA control tools
- Multi-turn follow-ups: "and the kitchen too"
- Hermes' full toolset (HA control, web, Spotify, calendar, memory, files, terminal) without leaving HA's voice flow

## How it fits together

```
"Okay Nabu" → Whisper (STT) → Hermes Conversation entity → Hermes bridge → hermes chat
                                                                                │
                                Voice PE  ◄── Piper (TTS)  ◄── reply text  ◄────┘
```

Two pieces have to be in place:

1. **The Hermes bridge** — a small Python service that runs on the Hermes host and exposes an OpenAI-compatible `/v1/chat/completions` endpoint over your LAN.
2. **This integration** — installed in Home Assistant, points at the bridge, registers as a conversation agent.

The first half of this README walks through the bridge; the second half installs and wires up the HA side.

## Prerequisites

- Home Assistant 2024.6 or newer (tested on 2026.4.4)
- An existing HA voice pipeline (Voice PE + Whisper + Piper, or any other STT/TTS combo)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed and working on a host on your LAN
- Both the HA host and the Hermes host on the same network
- Python 3 with `aiohttp` on the Hermes host: `pip install aiohttp`

---

## Part 1 — Set up the bridge

These steps run on the **Hermes host**, not the Home Assistant host.

### 1. Enable Home Assistant tools in Hermes

```bash
hermes tools enable homeassistant
```

This is what gives Hermes access to your HA entities and services. Hermes itself needs `HASS_TOKEN` configured separately — see the Hermes docs for that piece.

### 2. Find your Hermes machine's IP

**macOS:**
```bash
ipconfig getifaddr en0
```

**Linux:**
```bash
hostname -I | awk '{print $1}'
```

Write this IP down — you'll need it for both the bridge config and the HA integration.

### 3. Get the bridge script

The bridge script ships with the `hermes-ha-voice-bridge` skill:

```bash
ls ~/.hermes/skills/smart-home/hermes-ha-voice-bridge/scripts/
```

If the skill isn't installed, ask Hermes: "load the hermes-ha-voice-bridge skill and give me the bridge.py script." For convenience, copy it somewhere durable:

```bash
mkdir -p ~/.hermes/scripts
cp ~/.hermes/skills/smart-home/hermes-ha-voice-bridge/scripts/ha_voice_bridge.py ~/.hermes/scripts/
```

The rest of this guide assumes the bridge lives at `~/.hermes/scripts/ha_voice_bridge.py`.

### 4. Configure the bridge

Open the script and check the top section:

```python
HOST = os.environ.get("HERMES_BRIDGE_HOST", "YOUR_MAC_IP")
PORT = int(os.environ.get("HERMES_BRIDGE_PORT", "8645"))
```

Replace `YOUR_MAC_IP` with the IP from step 2, or leave it and use environment variables instead.

### 5. Start the bridge

```bash
python3 ~/.hermes/scripts/ha_voice_bridge.py --debug
```

You should see:

```
[bridge] Starting on http://192.168.x.x:8645
```

Test it from another terminal:

```bash
curl -s http://YOUR_IP:8645/health
# → {"status": "ok", "service": "hermes-voice-bridge"}
```

### 6. Make it permanent

#### macOS (launchd)

Create `~/Library/LaunchAgents/com.hermes.voice-bridge.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.voice-bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/YOU/.hermes/scripts/ha_voice_bridge.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HERMES_BRIDGE_HOST</key>
        <string>192.168.X.X</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/YOU</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/YOU/.hermes</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOU/.hermes/logs/bridge.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOU/.hermes/logs/bridge.log</string>
</dict>
</plist>
```

Replace the placeholders, then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.hermes.voice-bridge.plist
```

#### Linux (systemd)

Create `~/.config/systemd/user/hermes-bridge.service`:

```ini
[Unit]
Description=Hermes HA Voice Bridge
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/YOU/.hermes/scripts/ha_voice_bridge.py
Environment=HERMES_BRIDGE_HOST=192.168.X.X
Environment=HERMES_BRIDGE_PORT=8645
WorkingDirectory=/home/YOU/.hermes
Restart=always
RestartSec=5
StandardOutput=append:/home/YOU/.hermes/logs/bridge.log
StandardError=append:/home/YOU/.hermes/logs/bridge.log

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-bridge
systemctl --user status hermes-bridge
```

To keep it running after logout:

```bash
sudo loginctl enable-linger $USER
```

---

## Part 2 — Install the HA integration

### Install via HACS

1. HACS → ⋮ (three-dot menu) → **Custom repositories**
2. URL: `https://github.com/sj-unit72/hass-hermes`
3. Category: **Integration** → **Add**
4. Find "Hermes Conversation" in the HACS list, install, then **restart Home Assistant**.

### Manual install

Copy `custom_components/hermes/` into `<HA config>/custom_components/hermes/` and restart Home Assistant.

### Configure

1. Settings → **Devices & services** → **Add Integration** → search "Hermes Conversation".
2. Fill in:

| Field | Default | Notes |
|---|---|---|
| Bridge URL | `http://192.168.1.100:8645` | Replace with the IP of the machine running the bridge |
| Model | `hermes-agent` | Sent in the OpenAI request body |
| Timeout (s) | `60` | Raise to 90+ if Hermes runs heavy tool chains |
| System prompt | (default supplied) | Editable later via the integration's options |

Setup hits `/v1/models` on the bridge to verify reachability; if it can't connect you'll see "Could not reach the Hermes bridge."

### Wire it into your pipeline

Settings → **Voice assistants** → click your existing pipeline → set **Conversation agent** to **Hermes**. Don't touch STT or TTS — they keep doing what they were doing.

### Test

Test the typed path first — it isolates the integration from voice-pipeline behavior:

1. Settings → Voice assistants → click your pipeline → chat bubble icon (top-right of the dialog).
2. Type:
   - "What lights are on in the kitchen?"
   - "Turn them off." — if this works, multi-turn context is plumbed end-to-end.
3. Then voice: "Okay Nabu, what lights are on in the kitchen?" → wait for the reply → "turn them off."
   - For follow-ups to work over voice, the pipeline session needs to stay open between turns. If the LED goes dark right after Hermes replies, you'll need to re-wake — open an issue and a `continue_conversation: true` option will be added.

## Options

Settings → Devices & services → Hermes Conversation → **Configure** to tweak:

- **Model** — usually leave `hermes-agent`.
- **Timeout** — raise if you see "Hermes took too long to respond."
- **System prompt** — change personality / output guidance.

## Multi-turn behavior

History is kept per HA `conversation_id`, capped at 10 user/assistant exchanges. A new conversation_id (timeout, fresh wake, restart) starts fresh history. Up to 50 active conversations are tracked in an LRU cache; older ones are evicted automatically. The full history is shipped on every request — the bridge builds a transcript and feeds it to Hermes so follow-ups have context.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Bridge won't start | `pip install aiohttp` on the Hermes host |
| Setup fails with "Could not reach the Hermes bridge" | Bridge isn't running, URL is wrong, or HA host can't reach it. `curl http://<ip>:8645/health` from the HA host. If HA is in Docker, use the host's LAN IP, not `127.0.0.1`. |
| "Hermes is not reachable right now." (spoken) | Bridge stopped after setup succeeded. Check bridge logs (`~/.hermes/logs/bridge.log`). |
| "Hermes took too long to respond." | Raise the timeout in the integration's options. Default 60s; some tool chains need 90–120s. |
| "Hermes returned a malformed response." | Bridge returned non-OpenAI JSON. Update the bridge to the latest version. |
| Follow-ups don't work | Test typed first. If typed works but voice doesn't, the pipeline is closing the session between turns — file an issue. If neither works, `tail -f ~/.hermes/logs/bridge.log` and look for `openai query (N msgs)` — `N` should be > 1 on follow-up turns. |

HA-side logs: Settings → System → **Logs** → filter on `custom_components.hermes`. Bridge-side logs: `tail -f ~/.hermes/logs/bridge.log` on the bridge host.

## Uninstall

Bridge:

```bash
# macOS
launchctl unload ~/Library/LaunchAgents/com.hermes.voice-bridge.plist

# Linux
systemctl --user disable --now hermes-bridge
```

HA integration:

1. Settings → Devices & services → Hermes Conversation → Delete.
2. Re-point your pipeline's Conversation agent at "Home Assistant" (or another agent) so voice keeps working.
3. (Optional) HACS → Hermes Conversation → Remove.

## License

MIT — see [LICENSE](LICENSE).
