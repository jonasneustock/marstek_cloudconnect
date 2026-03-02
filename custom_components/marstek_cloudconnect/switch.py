from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MarstekBaseEntity, MarstekRuntimeData


@dataclass(frozen=True, kw_only=True)
class MarstekSwitchDescription(SwitchEntityDescription):
    command: str
    value_key: str
    exists_fn: Callable[[str], bool]


SWITCH_DESCRIPTIONS: tuple[MarstekSwitchDescription, ...] = (
    MarstekSwitchDescription(
        key="grid_connection_ban",
        translation_key="grid_connection_ban",
        command="grid-connection-ban",
        value_key="grid_connection_ban",
        exists_fn=lambda device_type: device_type.startswith("HMI"),
    ),
    MarstekSwitchDescription(
        key="surplus_feed_in",
        translation_key="surplus_feed_in",
        command="surplus-feed-in",
        value_key="surplus_feed_in_enabled",
        exists_fn=lambda device_type: any(device_type.startswith(prefix) for prefix in ("JPLS", "HMM", "HMN")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: MarstekRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator
    known_entities: set[tuple[str, str]] = set()

    def _build_entities() -> list[MarstekCommandSwitch]:
        entities: list[MarstekCommandSwitch] = []
        for device_id, device in coordinator.data.items():
            for description in SWITCH_DESCRIPTIONS:
                if not description.exists_fn(device.device_type):
                    continue
                key = (device_id, description.key)
                if key in known_entities:
                    continue
                known_entities.add(key)
                entities.append(MarstekCommandSwitch(coordinator, device_id, description))
        return entities

    async_add_entities(_build_entities())

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class MarstekCommandSwitch(MarstekBaseEntity, SwitchEntity):
    entity_description: MarstekSwitchDescription

    def __init__(self, coordinator, device_id: str, description: MarstekSwitchDescription) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        return bool(self._device.telemetry.get(self.entity_description.value_key, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(self._device_id, self.entity_description.command, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_command(self._device_id, self.entity_description.command, False)

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
