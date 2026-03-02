from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MarstekApiClient, MarstekApiError, MarstekAuthError
from .const import (
    CONF_BROKER_PASSWORD,
    CONF_BROKER_URL,
    CONF_BROKER_USERNAME,
    CONF_BASE_URL,
    CONF_ENABLE_TRANSPORT,
    CONF_MAILBOX,
    CONF_SCAN_INTERVAL,
    DEFAULT_BROKER_URL,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            mailbox = user_input[CONF_MAILBOX].strip()
            await self.async_set_unique_id(mailbox.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = MarstekApiClient(session, user_input[CONF_BASE_URL])
            try:
                await api.fetch_devices(mailbox=mailbox, password=user_input[CONF_PASSWORD])
            except MarstekAuthError:
                errors["base"] = "invalid_auth"
            except MarstekApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover - defensive catch
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=mailbox,
                    data={
                        CONF_MAILBOX: mailbox,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_BASE_URL: user_input[CONF_BASE_URL],
                        CONF_ENABLE_TRANSPORT: bool(user_input.get(CONF_ENABLE_TRANSPORT, False)),
                        CONF_BROKER_URL: user_input.get(CONF_BROKER_URL, DEFAULT_BROKER_URL),
                        CONF_BROKER_USERNAME: user_input.get(CONF_BROKER_USERNAME) or "",
                        CONF_BROKER_PASSWORD: user_input.get(CONF_BROKER_PASSWORD) or "",
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MAILBOX): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Optional(CONF_ENABLE_TRANSPORT, default=False): bool,
                vol.Optional(CONF_BROKER_URL, default=DEFAULT_BROKER_URL): str,
                vol.Optional(CONF_BROKER_USERNAME): str,
                vol.Optional(CONF_BROKER_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> MarstekOptionsFlow:
        return MarstekOptionsFlow(config_entry)


class MarstekOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Required(
                    CONF_ENABLE_TRANSPORT,
                    default=bool(self._entry.options.get(CONF_ENABLE_TRANSPORT, False)),
                ): bool,
                vol.Required(
                    CONF_BROKER_URL,
                    default=str(self._entry.options.get(CONF_BROKER_URL, DEFAULT_BROKER_URL)),
                ): str,
                vol.Optional(
                    CONF_BROKER_USERNAME,
                    default=self._entry.options.get(CONF_BROKER_USERNAME, ""),
                ): str,
                vol.Optional(
                    CONF_BROKER_PASSWORD,
                    default=self._entry.options.get(CONF_BROKER_PASSWORD, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
