from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MarstekBaseEntity, MarstekRuntimeData


@dataclass(frozen=True, kw_only=True)
class MarstekNumberDescription(NumberEntityDescription):
    command: str
    exists_fn: Callable[[str], bool]
    value_key: str


NUMBER_DESCRIPTIONS: tuple[MarstekNumberDescription, ...] = (
    MarstekNumberDescription(
        key="maximum_output_power",
        translation_key="maximum_output_power",
        command="max-output-power",
        value_key="maximum_output_power",
        native_min_value=0,
        native_max_value=800,
        native_step=1,
        native_unit_of_measurement="W",
        exists_fn=lambda device_type: device_type.startswith("HMI"),
    ),
    MarstekNumberDescription(
        key="depth_of_discharge",
        translation_key="depth_of_discharge",
        command="discharge-depth",
        value_key="depth_of_discharge",
        native_min_value=30,
        native_max_value=88,
        native_step=1,
        native_unit_of_measurement="%",
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

    def _build_entities() -> list[MarstekCommandNumber]:
        entities: list[MarstekCommandNumber] = []
        for device_id, device in coordinator.data.items():
            for description in NUMBER_DESCRIPTIONS:
                if not description.exists_fn(device.device_type):
                    continue
                key = (device_id, description.key)
                if key in known_entities:
                    continue
                known_entities.add(key)
                entities.append(MarstekCommandNumber(coordinator, device_id, description))
        return entities

    async_add_entities(_build_entities())

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class MarstekCommandNumber(MarstekBaseEntity, NumberEntity):
    entity_description: MarstekNumberDescription

    def __init__(self, coordinator, device_id: str, description: MarstekNumberDescription) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        value = self._device.telemetry.get(self.entity_description.value_key)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_send_command(
            self._device_id,
            self.entity_description.command,
            int(value),
        )

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
