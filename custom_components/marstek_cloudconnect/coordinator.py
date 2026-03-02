from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MarstekApiClient, MarstekApiError
from .const import (
    BMS_POLL_INTERVAL_SECONDS,
    CONF_ENABLE_TRANSPORT,
    CONF_MAILBOX,
    CONF_PROFILES_PATH,
    DEFAULT_PROFILES_PATH,
    DEFAULT_SCAN_INTERVAL,
)
from .models import CloudDevice
from .parser.command_builder import build_command_payload
from .parser.device_parser import parse_payload
from .transport import MarstekCloudTransport

_LOGGER = logging.getLogger(__name__)
_TIME_PERIOD_COMMAND_RE = re.compile(r"^time-period/(?P<index>[0-4])/(?P<field>start-time|end-time|weekday|power|enabled)$")


class MarstekCoordinator(DataUpdateCoordinator[dict[str, CloudDevice]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: MarstekApiClient,
    ) -> None:
        self.entry = entry
        self.api = api
        self.transport: MarstekCloudTransport | None = None
        self._bms_poll_task: asyncio.Task | None = None

        scan_interval = int(entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=f"marstek_cloudconnect_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, CloudDevice]:
        mailbox = self.entry.data[CONF_MAILBOX]
        password = self.entry.data[CONF_PASSWORD]

        try:
            devices = await self.api.fetch_devices(mailbox=mailbox, password=password)
        except MarstekApiError as err:
            raise UpdateFailed(str(err)) from err

        previous = self.data if self.data else {}
        for device in devices:
            old = previous.get(device.device_id)
            if old is not None:
                device.telemetry = dict(old.telemetry)
                device.raw_values = dict(old.raw_values)
                device.last_payload = old.last_payload
                device.last_topic = old.last_topic
                device.last_update = old.last_update
                device.available = old.available
                _derive_device_metrics(device)

        transport_enabled = bool(
            self.entry.options.get(CONF_ENABLE_TRANSPORT, self.entry.data.get(CONF_ENABLE_TRANSPORT, False))
        )

        if transport_enabled:
            profiles_path = str(
                self.entry.options.get(
                    CONF_PROFILES_PATH,
                    self.entry.data.get(CONF_PROFILES_PATH, DEFAULT_PROFILES_PATH),
                )
            )
            await self._async_start_transport(devices, profiles_path)
            self._ensure_bms_poll_task()
        else:
            await self._async_stop_transport()

        return {device.device_id: device for device in devices}

    async def async_shutdown(self) -> None:
        await self._async_stop_transport()

    def handle_transport_message(self, topic: str, payload: str) -> None:
        target = self._find_device_by_topic(topic)
        if target is None:
            _LOGGER.debug("Ignoring message from unknown topic: %s", topic)
            return

        raw_values, parsed = parse_payload(target.device_type, payload)
        target.raw_values.update(raw_values)
        target.telemetry.update(parsed)
        _derive_device_metrics(target)
        target.mark_message(topic=topic, payload=payload)
        self.async_set_updated_data(dict(self.data))

    async def async_send_command(
        self,
        device_id: str,
        command: str,
        value: str | int | bool | dict[str, Any] | None = None,
    ) -> None:
        device = self.data.get(device_id)
        if device is None:
            raise ValueError(f"Unknown device id: {device_id}")

        payload = build_command_payload(
            device.device_type,
            command,
            value,
            telemetry=device.telemetry,
        )

        if self.transport is None:
            raise RuntimeError("Cloud transport is disabled")

        await self.transport.async_publish_command(device, payload)
        self._apply_optimistic_state(device, command, value)
        self.async_set_updated_data(dict(self.data))

    async def _async_start_transport(self, devices: list[CloudDevice], profiles_path: str) -> None:
        if self.transport is None:
            self.transport = MarstekCloudTransport(self.hass, self.handle_transport_message)

        try:
            await self.transport.async_start(devices, profiles_path)
        except Exception as err:  # pragma: no cover - external IO
            _LOGGER.warning("Transport start failed: %s", err)

    async def _async_stop_transport(self) -> None:
        await self._async_stop_bms_poll_task()

        if self.transport is None:
            return

        try:
            await self.transport.async_stop()
        finally:
            self.transport = None

    def _ensure_bms_poll_task(self) -> None:
        if self._bms_poll_task and not self._bms_poll_task.done():
            return
        self._bms_poll_task = self.hass.async_create_task(self._async_bms_poll_loop())

    async def _async_stop_bms_poll_task(self) -> None:
        task = self._bms_poll_task
        if task is None:
            return
        self._bms_poll_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _async_bms_poll_loop(self) -> None:
        await asyncio.sleep(5)
        while True:
            await self._async_poll_bms_once()
            await asyncio.sleep(BMS_POLL_INTERVAL_SECONDS)

    async def _async_poll_bms_once(self) -> None:
        if self.transport is None:
            return
        for device in self.data.values():
            if not _is_jupiter_device(device):
                continue
            try:
                await self.transport.async_publish_command(device, "cd=14")
            except Exception as err:  # pragma: no cover - external IO
                _LOGGER.debug("BMS poll request failed for %s: %s", device.device_id, err)

    def _find_device_by_topic(self, topic: str) -> CloudDevice | None:
        for device in self.data.values():
            expected = f"{device.topic_prefix}{device.device_type}/device/{device.remote_id}/ctrl"
            if topic == expected:
                return device
        return None

    def _apply_optimistic_state(
        self,
        device: CloudDevice,
        command: str,
        value: str | int | bool | dict[str, Any] | None,
    ) -> None:
        if command == "max-output-power":
            device.telemetry["maximum_output_power"] = _normalize_int(value)
        elif command == "mode":
            device.telemetry["mode"] = str(value)
        elif command == "grid-connection-ban":
            device.telemetry["grid_connection_ban"] = _normalize_bool(value)
        elif command == "working-mode":
            device.telemetry["working_mode"] = str(value)
        elif command == "surplus-feed-in":
            device.telemetry["surplus_feed_in_enabled"] = _normalize_bool(value)
        elif command == "discharge-depth":
            device.telemetry["depth_of_discharge"] = _normalize_int(value)
        elif command == "sync-time":
            device.telemetry["last_sync_time_command"] = True
        elif command.startswith("time-period/"):
            _apply_time_period_optimistic(device, command, value)

        _derive_device_metrics(device)


def _derive_device_metrics(device: CloudDevice) -> None:
    pv_values = []
    for key in ("pv1_power", "pv2_power", "pv3_power", "pv4_power"):
        value = device.telemetry.get(key)
        if isinstance(value, (int, float)):
            pv_values.append(float(value))
    if pv_values:
        device.telemetry["solar_total_power"] = int(sum(pv_values))

    voltage = device.telemetry.get("battery_voltage")
    current = device.telemetry.get("battery_current")
    if isinstance(voltage, (int, float)) and isinstance(current, (int, float)):
        power = float(voltage) * float(current)
        status = device.telemetry.get("battery_working_status")
        if status == "charging":
            power = -abs(power)
        elif status == "discharging":
            power = abs(power)
        device.telemetry["battery_power"] = round(power, 2)


def _normalize_bool(value: str | int | bool | dict[str, Any] | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in {"1", "true", "on", "yes"}
    return False


def _normalize_int(value: str | int | bool | dict[str, Any] | None) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _is_jupiter_device(device: CloudDevice) -> bool:
    return any(device.device_type.startswith(prefix) for prefix in ("JPLS", "HMM", "HMN"))


def _apply_time_period_optimistic(
    device: CloudDevice,
    command: str,
    value: str | int | bool | dict[str, Any] | None,
) -> None:
    match = _TIME_PERIOD_COMMAND_RE.match(command)
    if not match:
        return

    index = int(match.group("index"))
    field = match.group("field")

    raw_periods = device.telemetry.setdefault("time_periods", [])
    if not isinstance(raw_periods, list):
        raw_periods = []
        device.telemetry["time_periods"] = raw_periods

    while len(raw_periods) <= index:
        raw_periods.append(
            {
                "start_time": "0:00",
                "end_time": "0:00",
                "weekday": "",
                "power": 0,
                "enabled": False,
            }
        )

    period = raw_periods[index]
    if not isinstance(period, dict):
        period = {
            "start_time": "0:00",
            "end_time": "0:00",
            "weekday": "",
            "power": 0,
            "enabled": False,
        }
        raw_periods[index] = period

    if field == "start-time" and isinstance(value, str):
        period["start_time"] = value
    elif field == "end-time" and isinstance(value, str):
        period["end_time"] = value
    elif field == "weekday" and isinstance(value, str):
        period["weekday"] = value
    elif field == "power":
        period["power"] = _normalize_int(value)
    elif field == "enabled":
        period["enabled"] = _normalize_bool(value)
