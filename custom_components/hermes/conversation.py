"""Hermes conversation agent."""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any, Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid as ulid_util

from .const import (
    CHAT_COMPLETIONS_PATH,
    CONF_MODEL,
    CONF_SYSTEM_PROMPT,
    CONF_TIMEOUT,
    CONF_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT,
    MAX_HISTORY_EXCHANGES,
    MAX_TRACKED_CONVERSATIONS,
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
    """Forwards user utterances to the local Hermes bridge with history."""

    _attr_has_entity_name = True
    _attr_name = "Hermes"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._history: OrderedDict[str, list[dict[str, str]]] = OrderedDict()

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    def _get_history(self, conversation_id: str) -> list[dict[str, str]]:
        """LRU-cached per-conversation message history (no system prompt)."""
        if conversation_id in self._history:
            self._history.move_to_end(conversation_id)
            return self._history[conversation_id]
        history: list[dict[str, str]] = []
        self._history[conversation_id] = history
        while len(self._history) > MAX_TRACKED_CONVERSATIONS:
            self._history.popitem(last=False)
        return history

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Send the utterance plus prior context to the bridge."""
        url = self._entry.data[CONF_URL].rstrip("/") + CHAT_COMPLETIONS_PATH
        model = self._entry.options.get(CONF_MODEL, DEFAULT_MODEL)
        timeout = self._entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        system_prompt = self._entry.options.get(
            CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT
        )

        conversation_id = user_input.conversation_id or ulid_util.ulid_now()
        history = self._get_history(conversation_id)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if user_input.extra_system_prompt:
            messages.append(
                {"role": "system", "content": user_input.extra_system_prompt}
            )
        messages.extend(history)
        messages.append({"role": "user", "content": user_input.text})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        session = async_get_clientsession(self.hass)
        reply: str
        try:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
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
        else:
            history.append({"role": "user", "content": user_input.text})
            history.append({"role": "assistant", "content": reply})
            _trim_history(history)

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(reply)
        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
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
        parts = [
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        joined = "".join(parts).strip()
        return joined or "(empty response)"
    raise ValueError("unrecognized content shape")


def _trim_history(history: list[dict[str, str]]) -> None:
    """Cap history at MAX_HISTORY_EXCHANGES user/assistant pairs."""
    max_msgs = MAX_HISTORY_EXCHANGES * 2
    if len(history) > max_msgs:
        del history[: len(history) - max_msgs]
