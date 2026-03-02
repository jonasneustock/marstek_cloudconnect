from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any


_TIME_PERIOD_COMMAND_RE = re.compile(r"^time-period/(?P<index>[0-4])/(?P<field>start-time|end-time|weekday|power|enabled)$")


@dataclass(slots=True)
class JupiterTimePeriod:
    start_time: str = "0:00"
    end_time: str = "0:00"
    weekday: str = ""
    power: int = 0
    enabled: bool = False


def build_command_payload(
    device_type: str,
    command: str,
    value: str | int | bool | dict[str, Any] | None = None,
    telemetry: dict[str, object] | None = None,
) -> str:
    base = device_type.split("-", maxsplit=1)[0].upper()

    if command == "refresh":
        return "cd=1"

    if base == "HMI":
        return _build_hmi(command, value)
    if base in {"JPLS", "HMM", "HMN"}:
        return _build_jupiter(command, value, telemetry)

    raise ValueError(f"Unsupported command '{command}' for device type '{device_type}'")


def _normalize_bool(value: str | int | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in {"1", "true", "on", "yes"}
    return False


def _to_int(value: str | int | bool | None) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, str):
        return int(value)
    raise ValueError("Value is required")


def _build_hmi(command: str, value: str | int | bool | dict[str, Any] | None) -> str:
    if command == "max-output-power":
        return f"cd=8,p1={_to_int(value)}"

    if command == "mode":
        mode_raw = str(value)
        mode_map = {"default": 0, "b2500Boost": 1, "reverseCurrentProtection": 2}
        if mode_raw not in mode_map:
            raise ValueError("Invalid HMI mode")
        return f"cd=11,p1={mode_map[mode_raw]}"

    if command == "grid-connection-ban":
        enabled = 1 if _normalize_bool(value) else 0
        return f"cd=22,p1={enabled}"

    raise ValueError(f"Unsupported HMI command: {command}")


def _build_jupiter(
    command: str,
    value: str | int | bool | dict[str, Any] | None,
    telemetry: dict[str, object] | None,
) -> str:
    if command == "working-mode":
        mode = str(value)
        mode_map = {"automatic": 1, "manual": 2}
        if mode not in mode_map:
            raise ValueError("Invalid Jupiter working mode")
        return f"cd=2,md={mode_map[mode]}"

    if command == "surplus-feed-in":
        enabled = 1 if _normalize_bool(value) else 0
        return f"cd=13,full_d={enabled}"

    if command == "discharge-depth":
        depth = _to_int(value)
        if depth < 30 or depth > 88:
            raise ValueError("Depth of discharge must be between 30 and 88")
        return f"cd=56,dod={depth}"

    if command == "factory-reset":
        return "cd=5,rs=2"

    if command == "sync-time":
        return _build_jupiter_sync_time(value)

    time_period_match = _TIME_PERIOD_COMMAND_RE.match(command)
    if time_period_match:
        index = int(time_period_match.group("index"))
        field = time_period_match.group("field")
        return _build_jupiter_time_period(index=index, field=field, value=value, telemetry=telemetry)

    raise ValueError(f"Unsupported Jupiter command: {command}")


def _build_jupiter_sync_time(value: str | int | bool | dict[str, Any] | None) -> str:
    payload: dict[str, Any] = {}
    if isinstance(value, dict):
        payload = value
    elif isinstance(value, str) and value.strip().startswith("{"):
        payload = json.loads(value)

    if payload:
        required = ("yy", "mm", "rr", "hh", "mn")
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(f"Missing sync-time fields: {', '.join(missing)}")
        return (
            "cd=4,"
            f"yy={int(payload['yy'])},"
            f"mm={int(payload['mm'])},"
            f"rr={int(payload['rr'])},"
            f"hh={int(payload['hh'])},"
            f"mn={int(payload['mn'])}"
        )

    now = datetime.now()
    return (
        "cd=4,"
        f"yy={now.year},"
        f"mm={now.month - 1},"
        f"rr={now.day},"
        f"hh={now.hour},"
        f"mn={now.minute}"
    )


def _build_jupiter_time_period(
    *,
    index: int,
    field: str,
    value: str | int | bool | dict[str, Any] | None,
    telemetry: dict[str, object] | None,
) -> str:
    periods = _parse_periods(telemetry)
    period = periods[index]

    if field == "start-time":
        if not isinstance(value, str) or not _is_time(value):
            raise ValueError("start-time must be in H:MM or HH:MM format")
        period.start_time = value
    elif field == "end-time":
        if not isinstance(value, str) or not _is_time(value):
            raise ValueError("end-time must be in H:MM or HH:MM format")
        period.end_time = value
    elif field == "weekday":
        if not isinstance(value, str) or not re.match(r"^[0-6]*$", value):
            raise ValueError("weekday must only contain digits 0..6")
        period.weekday = value
    elif field == "power":
        power = _to_int(value)
        if power < 0 or power > 800:
            raise ValueError("power must be between 0 and 800")
        period.power = power
    elif field == "enabled":
        period.enabled = _normalize_bool(value)
    else:  # pragma: no cover - exhaustive guard
        raise ValueError(f"Unknown time-period field: {field}")

    mode = str((telemetry or {}).get("working_mode", "automatic"))
    md = 2 if mode == "manual" else 1
    weekday_mask = _weekday_set_to_mask(period.weekday)
    enabled = 1 if period.enabled else 0
    return (
        "cd=3,"
        f"md={md},"
        f"nm={index},"
        f"bt={period.start_time},"
        f"et={period.end_time},"
        f"wk={weekday_mask},"
        f"vv={period.power},"
        f"as={enabled}"
    )


def _parse_periods(telemetry: dict[str, object] | None) -> list[JupiterTimePeriod]:
    raw_periods = telemetry.get("time_periods") if telemetry else None
    periods: list[JupiterTimePeriod] = [JupiterTimePeriod() for _ in range(5)]
    if not isinstance(raw_periods, list):
        return periods

    for index, raw in enumerate(raw_periods[:5]):
        if not isinstance(raw, dict):
            continue
        period = periods[index]
        start_time = raw.get("start_time")
        end_time = raw.get("end_time")
        weekday = raw.get("weekday")
        power = raw.get("power")
        enabled = raw.get("enabled")

        if isinstance(start_time, str) and _is_time(start_time):
            period.start_time = start_time
        if isinstance(end_time, str) and _is_time(end_time):
            period.end_time = end_time
        if isinstance(weekday, str) and re.match(r"^[0-6]*$", weekday):
            period.weekday = weekday
        if isinstance(power, int):
            period.power = power
        if isinstance(enabled, bool):
            period.enabled = enabled

    return periods


def _is_time(value: str) -> bool:
    return bool(re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", value))


def _weekday_set_to_mask(weekday_set: str) -> int:
    mask = 0
    for day in weekday_set:
        mask |= 1 << int(day)
    return mask
