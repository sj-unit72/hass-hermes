"""Constants for the Hermes Conversation integration."""

from __future__ import annotations

DOMAIN = "hermes"

CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_TIMEOUT = "timeout"
CONF_MODEL = "model"

DEFAULT_URL = "http://192.168.86.83:8645"
DEFAULT_TIMEOUT = 60
DEFAULT_MODEL = "hermes"

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"
