from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MarstekBaseEntity, MarstekRuntimeData
from .models import CloudDevice


@dataclass(frozen=True, kw_only=True)
class MarstekSensorDescription(SensorEntityDescription):
    value_fn: Callable[[CloudDevice], str | int | float | None]
    exists_fn: Callable[[CloudDevice], bool] = lambda _device: True


SENSOR_DESCRIPTIONS: tuple[MarstekSensorDescription, ...] = (
    MarstekSensorDescription(
        key="device_type",
        translation_key="device_type",
        value_fn=lambda device: device.device_type,
    ),
    MarstekSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        value_fn=lambda device: device.version_raw,
    ),
    MarstekSensorDescription(
        key="remote_topic_id",
        translation_key="remote_topic_id",
        value_fn=lambda device: device.remote_id,
    ),
    MarstekSensorDescription(
        key="daily_energy_generated",
        translation_key="daily_energy_generated",
        native_unit_of_measurement="kWh",
        value_fn=lambda device: _as_number(device.telemetry.get("daily_energy_generated")),
        exists_fn=lambda device: "daily_energy_generated" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="total_energy_generated",
        translation_key="total_energy_generated",
        native_unit_of_measurement="kWh",
        value_fn=lambda device: _as_number(device.telemetry.get("total_energy_generated")),
        exists_fn=lambda device: "total_energy_generated" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="combined_power",
        translation_key="combined_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("combined_power")),
        exists_fn=lambda device: "combined_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="pv1_power",
        translation_key="pv1_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("pv1_power")),
        exists_fn=lambda device: "pv1_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="pv2_power",
        translation_key="pv2_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("pv2_power")),
        exists_fn=lambda device: "pv2_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="pv3_power",
        translation_key="pv3_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("pv3_power")),
        exists_fn=lambda device: "pv3_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="pv4_power",
        translation_key="pv4_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("pv4_power")),
        exists_fn=lambda device: "pv4_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="solar_total_power",
        translation_key="solar_total_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("solar_total_power")),
        exists_fn=lambda device: "solar_total_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement="%",
        value_fn=lambda device: _as_number(device.telemetry.get("battery_soc")),
        exists_fn=lambda device: "battery_soc" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("battery_power")),
        exists_fn=lambda device: "battery_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement="V",
        value_fn=lambda device: _as_number(device.telemetry.get("battery_voltage")),
        exists_fn=lambda device: "battery_voltage" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="battery_current",
        translation_key="battery_current",
        native_unit_of_measurement="A",
        value_fn=lambda device: _as_number(device.telemetry.get("battery_current")),
        exists_fn=lambda device: "battery_current" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="phase1_power",
        translation_key="phase1_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("phase1_power")),
        exists_fn=lambda device: "phase1_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="phase2_power",
        translation_key="phase2_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("phase2_power")),
        exists_fn=lambda device: "phase2_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="phase3_power",
        translation_key="phase3_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("phase3_power")),
        exists_fn=lambda device: "phase3_power" in device.telemetry,
    ),
    MarstekSensorDescription(
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement="W",
        value_fn=lambda device: _as_number(device.telemetry.get("total_power")),
        exists_fn=lambda device: "total_power" in device.telemetry,
    ),
)


def _as_number(value: object) -> int | float | None:
    if isinstance(value, (int, float)):
        return value
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: MarstekRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator

    known_entities: set[tuple[str, str]] = set()

    def _build_entities() -> list[MarstekDeviceSensor]:
        entities: list[MarstekDeviceSensor] = []
        for device_id, device in coordinator.data.items():
            for description in SENSOR_DESCRIPTIONS:
                if not description.exists_fn(device):
                    continue
                key = (device_id, description.key)
                if key in known_entities:
                    continue
                known_entities.add(key)
                entities.append(MarstekDeviceSensor(coordinator, device_id, description))
        return entities

    async_add_entities(_build_entities())

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class MarstekDeviceSensor(MarstekBaseEntity, SensorEntity):
    entity_description: MarstekSensorDescription

    def __init__(
        self,
        coordinator,
        device_id: str,
        description: MarstekSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

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

    @property
    def native_value(self):
        return self.entity_description.value_fn(self._device)
