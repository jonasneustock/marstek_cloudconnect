from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MarstekBaseEntity, MarstekRuntimeData


@dataclass(frozen=True, kw_only=True)
class MarstekSelectDescription(SelectEntityDescription):
    command: str
    value_key: str
    exists_fn: Callable[[str], bool]


SELECT_DESCRIPTIONS: tuple[MarstekSelectDescription, ...] = (
    MarstekSelectDescription(
        key="mi800_mode",
        translation_key="mi800_mode",
        command="mode",
        value_key="mode",
        options=["default", "b2500Boost", "reverseCurrentProtection"],
        exists_fn=lambda device_type: device_type.startswith("HMI"),
    ),
    MarstekSelectDescription(
        key="working_mode",
        translation_key="working_mode",
        command="working-mode",
        value_key="working_mode",
        options=["automatic", "manual"],
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

    def _build_entities() -> list[MarstekCommandSelect]:
        entities: list[MarstekCommandSelect] = []
        for device_id, device in coordinator.data.items():
            for description in SELECT_DESCRIPTIONS:
                if not description.exists_fn(device.device_type):
                    continue
                key = (device_id, description.key)
                if key in known_entities:
                    continue
                known_entities.add(key)
                entities.append(MarstekCommandSelect(coordinator, device_id, description))
        return entities

    async_add_entities(_build_entities())

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class MarstekCommandSelect(MarstekBaseEntity, SelectEntity):
    entity_description: MarstekSelectDescription

    def __init__(self, coordinator, device_id: str, description: MarstekSelectDescription) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        value = self._device.telemetry.get(self.entity_description.value_key)
        if isinstance(value, str) and value in self.options:
            return value
        return None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_send_command(self._device_id, self.entity_description.command, option)

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
