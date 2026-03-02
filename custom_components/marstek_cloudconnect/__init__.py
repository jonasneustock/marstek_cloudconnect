from __future__ import annotations

import logging
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MarstekApiClient, MarstekApiError
from .const import (
    ATTR_DEVICE_ID,
    CONF_BASE_URL,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH,
    SERVICE_SEND_COMMAND,
)
from .coordinator import MarstekCoordinator
from .entity import MarstekRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async def _handle_refresh(call: ServiceCall) -> None:
        entries = hass.config_entries.async_entries(DOMAIN)
        for item in entries:
            runtime: MarstekRuntimeData = hass.data[DOMAIN][item.entry_id]
            await runtime.coordinator.async_request_refresh()

    async def _handle_send_command(call: ServiceCall) -> None:
        target_device_id = call.data[ATTR_DEVICE_ID]
        command = call.data["command"]
        value = call.data.get("value")

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    value = json.loads(stripped)
                except json.JSONDecodeError:
                    pass
            elif stripped.lower() in {"true", "false"}:
                value = stripped.lower() == "true"
            else:
                try:
                    value = int(stripped)
                except ValueError:
                    value = stripped

        entries = hass.config_entries.async_entries(DOMAIN)
        for item in entries:
            runtime: MarstekRuntimeData = hass.data[DOMAIN][item.entry_id]
            if target_device_id in runtime.coordinator.data:
                await runtime.coordinator.async_send_command(target_device_id, command, value)
                return

        raise ValueError(f"Unknown device id: {target_device_id}")

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        hass.services.async_register(DOMAIN, SERVICE_SEND_COMMAND, _handle_send_command)

    session = async_get_clientsession(hass)
    api = MarstekApiClient(session, entry.data[CONF_BASE_URL])
    coordinator = MarstekCoordinator(hass, entry, api)

    try:
        await coordinator.async_config_entry_first_refresh()
    except MarstekApiError as err:
        raise ConfigEntryNotReady(f"Unable to initialize Marstek API: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = MarstekRuntimeData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.debug("Setup completed for entry %s", entry.entry_id)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: MarstekRuntimeData = hass.data[DOMAIN][entry.entry_id]
    await runtime.coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
            hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
            hass.data.pop(DOMAIN)
    return unload_ok
