from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MarstekBaseEntity, MarstekRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: MarstekRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator

    known_device_ids: set[str] = set()

    def _build_entities() -> list[ButtonEntity]:
        entities: list[ButtonEntity] = []
        for device_id, device in coordinator.data.items():
            if device_id in known_device_ids:
                continue
            known_device_ids.add(device_id)
            entities.append(MarstekRefreshButton(coordinator, device_id))
            if any(device.device_type.startswith(prefix) for prefix in ("JPLS", "HMM", "HMN")):
                entities.append(MarstekSyncTimeButton(coordinator, device_id))
                entities.append(MarstekFactoryResetButton(coordinator, device_id))
        return entities

    async_add_entities(_build_entities())

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class MarstekRefreshButton(MarstekBaseEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_refresh"
        self._attr_name = "Refresh"

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            model=device.device_type,
            manufacturer="Marstek",
            sw_version=device.version_raw,
        )

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class MarstekFactoryResetButton(MarstekBaseEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "factory_reset"

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_factory_reset"
        self._attr_name = "Factory Reset"

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            model=device.device_type,
            manufacturer="Marstek",
            sw_version=device.version_raw,
        )

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(self._device_id, "factory-reset", True)


class MarstekSyncTimeButton(MarstekBaseEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "sync_time"

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_sync_time"
        self._attr_name = "Sync Time"

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            model=device.device_type,
            manufacturer="Marstek",
            sw_version=device.version_raw,
        )

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(self._device_id, "sync-time", True)
