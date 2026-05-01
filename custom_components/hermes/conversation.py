"""Hermes conversation agent."""

from __future__ import annotations

import logging
from typing import Any, Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHAT_COMPLETIONS_PATH,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_TIMEOUT,
    CONF_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register the Hermes conversation entity."""
    async_add_entities([HermesConversationEntity(entry)])


class HermesConversationEntity(conversation.ConversationEntity):
    """Forwards user utterances to the local Hermes bridge."""

    _attr_has_entity_name = True
    _attr_name = "Hermes"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register this entity as a conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister on removal."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Send the utterance to the bridge and return the assistant reply."""
        url = self._entry.data[CONF_URL].rstrip("/") + CHAT_COMPLETIONS_PATH
        api_key = self._entry.data.get(CONF_API_KEY) or ""
        model = self._entry.options.get(CONF_MODEL, DEFAULT_MODEL)
        timeout = self._entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": user_input.text}],
            "stream": False,
        }

        session = async_get_clientsession(self.hass)
        reply: str
        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                reply = _extract_reply(data)
        except TimeoutError:
            _LOGGER.warning("Hermes bridge timed out after %ss", timeout)
            reply = "Hermes took too long to respond."
        except aiohttp.ClientResponseError as err:
            _LOGGER.error("Hermes bridge HTTP %s: %s", err.status, err.message)
            reply = f"Hermes returned an error ({err.status})."
        except aiohttp.ClientError as err:
            _LOGGER.error("Hermes bridge unreachable: %s", err)
            reply = "Hermes is not reachable right now."
        except (KeyError, ValueError, TypeError) as err:
            _LOGGER.error("Malformed response from Hermes bridge: %s", err)
            reply = "Hermes returned a malformed response."

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(reply)
        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )


def _extract_reply(data: dict[str, Any]) -> str:
    """Pull the assistant text out of an OpenAI-format response."""
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("no choices in response")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or "(empty response)"
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        joined = "".join(parts).strip()
        return joined or "(empty response)"
    raise ValueError("unrecognized content shape")
