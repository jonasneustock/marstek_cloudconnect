from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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

    def _build_entities() -> list[BinarySensorEntity]:
        entities: list[BinarySensorEntity] = []
        for device_id in coordinator.data:
            if device_id in known_device_ids:
                continue
            known_device_ids.add(device_id)
            entities.append(MarstekCqSupportBinarySensor(coordinator, device_id))
            entities.append(MarstekOnlineBinarySensor(coordinator, device_id))
        return entities

    async_add_entities(_build_entities())

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class MarstekCqSupportBinarySensor(MarstekBaseEntity, BinarySensorEntity):
    _attr_translation_key = "supports_cq"
    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_supports_cq"
        self._attr_name = "CQ Encryption Support"

    @property
    def is_on(self) -> bool:
        return bool(self._device.supports_cq)

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


class MarstekOnlineBinarySensor(MarstekBaseEntity, BinarySensorEntity):
    _attr_translation_key = "online"
    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_online"
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool:
        return bool(self._device.available)

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
