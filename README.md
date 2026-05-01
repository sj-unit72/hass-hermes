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

The Hermes Conversation entity is what this repo provides. The bridge runs on the Hermes host and exposes an OpenAI-compatible `/v1/chat/completions` endpoint.

## Prerequisites

- Home Assistant 2024.6 or newer (tested on 2026.4.4)
- An existing HA voice pipeline (Voice PE + Whisper + Piper, or any other STT/TTS combo)
- The **Hermes HA Voice Bridge** running and reachable on your LAN — see the bridge install guide on the Hermes side. The short version:
  ```bash
  hermes tools enable homeassistant
  python3 ~/.hermes/scripts/ha_voice_bridge.py
  ```
  Verify it's up from the HA host:
  ```bash
  curl http://<bridge-ip>:8645/health
  # → {"status":"ok","service":"hermes-voice-bridge"}
  ```

## Install via HACS

1. HACS → ⋮ (three-dot menu) → **Custom repositories**
2. URL: `https://github.com/sj-unit72/hass-hermes`
3. Category: **Integration** → **Add**
4. Find "Hermes Conversation" in the HACS list, install, then **restart Home Assistant**.

## Manual install

Copy `custom_components/hermes/` into `<HA config>/custom_components/hermes/` and restart Home Assistant.

## Configure

1. Settings → **Devices & services** → **Add Integration** → search "Hermes Conversation".
2. Fill in:

| Field | Default | Notes |
|---|---|---|
| Bridge URL | `http://192.168.1.100:8645` | Replace with the IP of the machine running the bridge |
| Model | `hermes-agent` | Sent in the OpenAI request body |
| Timeout (s) | `60` | Raise to 90+ if Hermes runs heavy tool chains |
| System prompt | (default supplied) | Editable later via the integration's options |

Setup hits `/v1/models` on the bridge to verify reachability; if it can't connect you'll see "Could not reach the Hermes bridge."

## Wire it into your pipeline

Settings → **Voice assistants** → click your existing pipeline → set **Conversation agent** to **Hermes**. Don't touch STT or TTS — they keep doing what they were doing.

## Test

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
| Setup fails with "Could not reach the Hermes bridge" | Bridge isn't running, URL is wrong, or HA host can't reach it. `curl http://<ip>:8645/health` from the HA host. If HA is in Docker, use the host's LAN IP, not `127.0.0.1`. |
| "Hermes is not reachable right now." (spoken) | Bridge stopped after setup succeeded. Check bridge logs (`~/.hermes/logs/bridge.log`). |
| "Hermes took too long to respond." | Raise the timeout in the integration's options. Default 60s; some tool chains need 90–120s. |
| "Hermes returned a malformed response." | Bridge returned non-OpenAI JSON. Update the bridge to the latest version. |
| Follow-ups don't work | Test typed first. If typed works but voice doesn't, the pipeline is closing the session between turns — file an issue. |

HA-side logs: Settings → System → **Logs** → filter on `custom_components.hermes`. Bridge-side logs: `tail -f ~/.hermes/logs/bridge.log` on the bridge host (look for `openai query (N msgs)` — `N` should be > 1 on follow-up turns).

## Uninstall

1. Settings → Devices & services → Hermes Conversation → Delete.
2. Re-point your pipeline's Conversation agent at "Home Assistant" (or another agent) so voice keeps working.
3. (Optional) HACS → Hermes Conversation → Remove.

The bridge runs independently; uninstall it on the Hermes side per its own guide.
