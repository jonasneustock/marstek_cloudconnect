from __future__ import annotations


def parse_payload(device_type: str, payload: str) -> tuple[dict[str, str], dict[str, object]]:
    values = _parse_key_values(payload)
    base = device_type.split("-", maxsplit=1)[0].upper()

    if base == "HMI":
        return values, _parse_hmi(values)
    if base == "HME":
        return values, _parse_ct002(values)
    if base in {"JPLS", "HMM", "HMN"}:
        return values, _parse_jupiter(values)

    return values, {}


def _parse_key_values(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in payload.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", maxsplit=1)
        values[key] = value
    return values


def _to_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _parse_bool_int(value: str | None) -> bool:
    return _to_int(value) == 1


def _parse_hmi(values: dict[str, str]) -> dict[str, object]:
    mode_map = {"0": "default", "1": "b2500Boost", "2": "reverseCurrentProtection"}
    mode_raw = values.get("mpt_m") or "0"
    data: dict[str, object] = {
        "daily_energy_generated": _to_float(values.get("ele_d")) / 100,
        "weekly_energy_generated": _to_float(values.get("ele_w")) / 100,
        "monthly_energy_generated": _to_float(values.get("ele_m")) / 100,
        "total_energy_generated": _to_float(values.get("ele_s")) / 100,
        "pv1_voltage": _to_float(values.get("pv1_v")) / 10,
        "pv1_current": _to_float(values.get("pv1_i")) / 10,
        "pv1_power": _to_int(values.get("pv1_p")),
        "pv1_status": _parse_bool_int(values.get("pv1_s")),
        "pv2_voltage": _to_float(values.get("pv2_v")) / 10,
        "pv2_current": _to_float(values.get("pv2_i")) / 10,
        "pv2_power": _to_int(values.get("pv2_p")),
        "pv2_status": _parse_bool_int(values.get("pv2_s")),
        "grid_frequency": _to_float(values.get("grd_f")) / 100,
        "grid_voltage": _to_float(values.get("grd_v")) / 10,
        "grid_status": _parse_bool_int(values.get("grd_s")),
        "grid_output_power": _to_int(values.get("grd_o")),
        "chip_temperature": _to_int(values.get("chp_t")),
        "error_type": _to_int(values.get("err_t")),
        "error_count": _to_int(values.get("err_c")),
        "error_details": _to_int(values.get("err_d")),
        "firmware_version": _to_int(values.get("ver_s")),
        "fc4_version": values.get("fc4_v"),
        "maximum_output_power": _to_int(values.get("pl")),
        "mode": mode_map.get(mode_raw, "default"),
        "grid_connection_ban": _parse_bool_int(values.get("gc")),
    }
    return {k: v for k, v in data.items() if v not in (None, "")}


def _parse_ct002(values: dict[str, str]) -> dict[str, object]:
    data: dict[str, object] = {
        "phase1_power": _to_int(values.get("pwr_a")),
        "phase2_power": _to_int(values.get("pwr_b")),
        "phase3_power": _to_int(values.get("pwr_c")),
        "total_power": _to_int(values.get("pwr_t")),
        "bluetooth_signal": _to_int(values.get("ble_s")),
        "wifi_rssi": _to_int(values.get("wif_r")),
        "fc4_version": values.get("fc4_v"),
        "firmware_version": _to_int(values.get("ver_v")),
        "wifi_status": _to_int(values.get("wif_s")),
    }
    return {k: v for k, v in data.items() if v not in (None, "")}


def _parse_jupiter(values: dict[str, str]) -> dict[str, object]:
    working_mode = "automatic" if values.get("wor_m") == "1" else "manual"
    battery_status_map = {"0": "keep", "1": "charging", "2": "discharging"}
    cel_status = values.get("cel_s", "")
    data: dict[str, object] = {
        "daily_charging_capacity": _to_float(values.get("ele_d")) / 100,
        "monthly_charging_capacity": _to_float(values.get("ele_m")) / 100,
        "yearly_charging_capacity": _to_float(values.get("ele_y")) / 100,
        "pv1_power": _to_int(values.get("pv1_p")),
        "pv2_power": _to_int(values.get("pv2_p")),
        "pv3_power": _to_int(values.get("pv3_p")),
        "pv4_power": _to_int(values.get("pv4_p")),
        "daily_discharge_capacity": _to_float(values.get("grd_d")) / 100,
        "monthly_discharge_capacity": _to_float(values.get("grd_m")) / 100,
        "combined_power": _to_int(values.get("grd_o")),
        "battery_soc": _to_int(values.get("cel_c")),
        "battery_energy": _to_float(values.get("cel_p")) / 100,
        "battery_working_status": battery_status_map.get(cel_status, "unknown"),
        "error_code": _to_int(values.get("err_t")),
        "working_mode": working_mode,
        "wifi_signal_strength": -_to_int(values.get("wif_s")),
        "surplus_feed_in_enabled": values.get("ful_d") == "1",
        "depth_of_discharge": _to_int(values.get("dod")),
        "alarm_code": _to_int(values.get("ala_c")),
        "time_periods": _parse_jupiter_time_periods(values),
    }
    return {k: v for k, v in data.items() if v not in (None, "")}


def _parse_jupiter_time_periods(values: dict[str, str]) -> list[dict[str, object]]:
    periods: list[dict[str, object]] = []
    for index in range(5):
        raw = values.get(f"tim_{index}")
        if not raw:
            continue
        parsed = _parse_time_period(raw)
        periods.append(parsed)
    return periods


def _parse_time_period(raw: str) -> dict[str, object]:
    parts = raw.split("|")
    if len(parts) < 7:
        return {
            "start_time": "0:00",
            "end_time": "0:00",
            "weekday": "",
            "power": 0,
            "enabled": False,
        }

    start_hour = _to_int(parts[0])
    start_minute = _to_int(parts[1])
    end_hour = _to_int(parts[2])
    end_minute = _to_int(parts[3])
    weekday_mask = _to_int(parts[4])
    power = _to_int(parts[5])
    enabled = parts[6] == "1"

    return {
        "start_time": f"{start_hour}:{start_minute:02d}",
        "end_time": f"{end_hour}:{end_minute:02d}",
        "weekday": _weekday_mask_to_set(weekday_mask),
        "power": power,
        "enabled": enabled,
    }


def _weekday_mask_to_set(mask: int) -> str:
    return "".join(str(index) for index in range(7) if mask & (1 << index))
