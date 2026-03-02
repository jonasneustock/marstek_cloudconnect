from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MarstekCoordinator


@dataclass(slots=True)
class MarstekRuntimeData:
    coordinator: MarstekCoordinator


class MarstekBaseEntity(CoordinatorEntity[MarstekCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MarstekCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def available(self) -> bool:
        return super().available and self._device_id in self.coordinator.data

    @property
    def _device(self):
        return self.coordinator.data[self._device_id]
