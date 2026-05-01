"""Config flow for the Hermes Conversation integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_MODEL,
    CONF_TIMEOUT,
    CONF_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    DEFAULT_URL,
    DOMAIN,
    MODELS_PATH,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_bridge(hass: HomeAssistant, url: str, api_key: str | None) -> None:
    """Hit the bridge's /v1/models endpoint to confirm reachability."""
    session = async_get_clientsession(hass)
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with session.get(
        url.rstrip("/") + MODELS_PATH,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()


class HermesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Prompt the user for the bridge URL and optional API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            try:
                await _validate_bridge(self.hass, url, user_input.get(CONF_API_KEY))
            except aiohttp.ClientResponseError as err:
                _LOGGER.warning("Bridge returned HTTP error: %s", err)
                errors["base"] = "invalid_auth" if err.status in (401, 403) else "cannot_connect"
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.warning("Bridge unreachable: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Hermes ({url})",
                    data={CONF_URL: url, CONF_API_KEY: user_input.get(CONF_API_KEY, "")},
                    options={
                        CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
                        CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=DEFAULT_URL): str,
                vol.Optional(CONF_API_KEY, default=""): str,
                vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): str,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=600)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HermesOptionsFlow()


class HermesOptionsFlow(OptionsFlow):
    """Allow tweaking model/timeout after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MODEL, default=current.get(CONF_MODEL, DEFAULT_MODEL)
                ): str,
                vol.Optional(
                    CONF_TIMEOUT, default=current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
