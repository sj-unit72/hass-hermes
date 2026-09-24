"""Constants for the Hermes Conversation integration."""

from __future__ import annotations

DOMAIN = "hermes"

CONF_URL = "url"
CONF_TIMEOUT = "timeout"
CONF_MODEL = "model"
CONF_API_KEY = "api_key"
CONF_SYSTEM_PROMPT = "system_prompt"

DEFAULT_URL = "http://192.168.1.100:8645"
DEFAULT_TIMEOUT = 60
DEFAULT_MODEL = "hermes-agent"
DEFAULT_SYSTEM_PROMPT = (
    "You are Hermes, a smart home voice assistant. "
    "Keep responses short and natural for spoken output. "
    "You can control Home Assistant devices when the user asks about one or requests an action. "
    "When the user's utterance is a routine name (good night, good morning, bedtime) or states "
    "a routine already ran, do NOT call tools to verify or re-run it: the Home Assistant script "
    "executes the actions deterministically and guards against redundant commands. "
    "Just reply conversationally."
)

MAX_HISTORY_EXCHANGES = 10
MAX_TRACKED_CONVERSATIONS = 50

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"
