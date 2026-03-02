from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import MarstekRuntimeData

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict:
    runtime: MarstekRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = runtime.coordinator

    return {
        "entry": async_redact_data(dict(config_entry.data), TO_REDACT),
        "options": dict(config_entry.options),
        "devices": {
            device_id: {
                "device_id": device.device_id,
                "mac_suffix": device.mac[-4:] if device.mac else None,
                "device_type": device.device_type,
                "name": device.name,
                "version": device.version_raw,
                "supports_cq": device.supports_cq,
                "broker_id": device.broker_id,
                "topic_prefix": device.topic_prefix,
                "last_topic": device.last_topic,
                "last_update": device.last_update.isoformat() if device.last_update else None,
            }
            for device_id, device in coordinator.data.items()
        },
        "active_profiles_path": coordinator.active_profiles_path,
        "profiles_auto_generated": coordinator.profiles_auto_generated,
        "profiles_generation_source": coordinator.profiles_generation_source,
        "profiles_bootstrap_error": coordinator.profiles_bootstrap_error,
        "last_update_success": coordinator.last_update_success,
    }
