# Hermes Conversation for Home Assistant

A custom Home Assistant integration that registers [Hermes](https://github.com/NousResearch/hermes-agent) as a conversation agent, so you can use it inside your Voice Assistant pipeline (Voice PE, mobile app, web, etc.).

It assumes you are already running the local Hermes voice bridge that exposes an OpenAI-compatible `POST /v1/chat/completions` endpoint (e.g. the bridge at `~/.hermes/scripts/ha_voice_bridge.py`). The integration is a thin client — Home Assistant handles STT/TTS, this entity handles brains.

## Architecture

```
Voice PE  ─►  Whisper (STT)  ─►  Hermes Conversation entity  ─►  Hermes bridge  ─►  Hermes agent
                                          │                                              │
                                          └────────────────────────────  Piper (TTS)  ◄──┘
```

Hermes itself can already control Home Assistant via its built-in `ha_call_service` tool (when `HASS_TOKEN` is set on the Hermes side), so device control works without any extra wiring on the HA side.

## Install via HACS

1. In HACS → Integrations → ⋮ → **Custom repositories**, add this repo as type "Integration".
2. Install **Hermes Conversation**.
3. Restart Home Assistant.
4. Settings → Devices & services → **Add Integration** → "Hermes Conversation".
5. Enter the bridge URL (default `http://192.168.86.83:8645`), optional API key, model name, and timeout.

## Manual install

Copy `custom_components/hermes/` into `/config/custom_components/hermes/` and restart Home Assistant. Then add the integration from the UI.

## Wire it into your voice pipeline

Settings → **Voice assistants** → pick your existing pipeline (the one already using Whisper + Piper) → set **Conversation agent** to *Hermes*. Leave STT and TTS untouched.

## Options

- **Bridge URL** — base URL of the bridge; the integration appends `/v1/chat/completions`.
- **API key** — only required if the bridge sets `API_SERVER_KEY`.
- **Model** — passed through in the OpenAI request body. The bridge currently ignores it (Hermes picks its own model), but it's preserved for forward compatibility.
- **Timeout** — seconds to wait for a reply. Default 60s; raise this if Hermes runs heavy tool chains.

## What it does not do (yet)

- It does not send conversation history; each turn ships only the latest user utterance. Hermes maintains its own session memory across calls, so this is intentional for now.
- It does not expose HA entities to the agent via the HA intent system. Hermes already controls HA via its own REST tools.
- It does not stream. The bridge accepts `stream: false` and returns the full reply.

## Troubleshooting

- **"Hermes is not reachable right now."** — the bridge is down or the URL is wrong. Hit `http://<bridge>/v1/models` from a browser to confirm.
- **"Hermes took too long to respond."** — raise the timeout in the integration's options.
- **Setup fails with `cannot_connect`** — same as above; the config flow validates by hitting `/v1/models` with a 10s timeout.
