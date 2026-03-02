from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.marstek_cloudconnect.button import MarstekFactoryResetButton, MarstekRefreshButton, MarstekSyncTimeButton
from custom_components.marstek_cloudconnect.number import MarstekCommandNumber, NUMBER_DESCRIPTIONS
from custom_components.marstek_cloudconnect.select import MarstekCommandSelect, SELECT_DESCRIPTIONS
from custom_components.marstek_cloudconnect.switch import MarstekCommandSwitch, SWITCH_DESCRIPTIONS


class _FakeCoordinator:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str, object]] = []
        self.refresh_calls = 0

    async def async_send_command(self, device_id: str, command: str, value=None) -> None:
        self.commands.append((device_id, command, value))

    async def async_request_refresh(self) -> None:
        self.refresh_calls += 1


@pytest.mark.asyncio
async def test_number_entity_sends_command() -> None:
    coordinator = _FakeCoordinator()
    entity = MarstekCommandNumber.__new__(MarstekCommandNumber)
    entity._coordinator = coordinator
    entity._device_id = "dev1"
    entity.entity_description = NUMBER_DESCRIPTIONS[0]

    await entity.async_set_native_value(450)

    assert coordinator.commands == [("dev1", "max-output-power", 450)]


@pytest.mark.asyncio
async def test_select_entity_sends_command() -> None:
    coordinator = _FakeCoordinator()
    entity = MarstekCommandSelect.__new__(MarstekCommandSelect)
    entity._coordinator = coordinator
    entity._device_id = "dev1"
    entity.entity_description = SELECT_DESCRIPTIONS[0]

    await entity.async_select_option("default")

    assert coordinator.commands == [("dev1", "mode", "default")]


@pytest.mark.asyncio
async def test_switch_entity_sends_on_and_off_commands() -> None:
    coordinator = _FakeCoordinator()
    entity = MarstekCommandSwitch.__new__(MarstekCommandSwitch)
    entity._coordinator = coordinator
    entity._device_id = "dev1"
    entity.entity_description = SWITCH_DESCRIPTIONS[0]

    await entity.async_turn_on()
    await entity.async_turn_off()

    assert coordinator.commands == [
        ("dev1", "grid-connection-ban", True),
        ("dev1", "grid-connection-ban", False),
    ]


@pytest.mark.asyncio
async def test_button_entities_send_expected_commands() -> None:
    coordinator = _FakeCoordinator()

    refresh = MarstekRefreshButton.__new__(MarstekRefreshButton)
    refresh._coordinator = coordinator
    refresh._device_id = "dev1"

    factory_reset = MarstekFactoryResetButton.__new__(MarstekFactoryResetButton)
    factory_reset._coordinator = coordinator
    factory_reset._device_id = "dev1"

    sync_time = MarstekSyncTimeButton.__new__(MarstekSyncTimeButton)
    sync_time._coordinator = coordinator
    sync_time._device_id = "dev1"

    await refresh.async_press()
    await factory_reset.async_press()
    await sync_time.async_press()

    assert coordinator.refresh_calls == 1
    assert coordinator.commands == [
        ("dev1", "factory-reset", True),
        ("dev1", "sync-time", True),
    ]
