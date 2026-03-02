from __future__ import annotations

from custom_components.marstek_cloudconnect.parser.device_parser import parse_payload


def test_parse_jupiter_bms_payload_only_sets_bms_related_keys() -> None:
    _, parsed = parse_payload("JPLS-1", "b_vol=5252,b_cur=63")

    assert parsed["battery_voltage"] == 52.52
    assert parsed["battery_current"] == 6.3
    assert "pv1_power" not in parsed
    assert "combined_power" not in parsed
