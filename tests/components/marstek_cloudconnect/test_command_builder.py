from __future__ import annotations

import pytest

from custom_components.marstek_cloudconnect.parser.command_builder import build_command_payload


def test_build_jupiter_sync_time_from_dict_value() -> None:
    payload = build_command_payload(
        "JPLS-1",
        "sync-time",
        {
            "yy": 2026,
            "mm": 2,
            "rr": 3,
            "hh": 14,
            "mn": 15,
        },
    )

    assert payload == "cd=4,yy=2026,mm=2,rr=3,hh=14,mn=15"


def test_build_jupiter_time_period_command_from_existing_state() -> None:
    telemetry = {
        "working_mode": "manual",
        "time_periods": [
            {
                "start_time": "12:00",
                "end_time": "23:59",
                "weekday": "0123456",
                "power": 800,
                "enabled": True,
            }
        ],
    }

    payload = build_command_payload(
        "JPLS-1",
        "time-period/0/power",
        350,
        telemetry=telemetry,
    )

    assert payload == "cd=3,md=2,nm=0,bt=12:00,et=23:59,wk=127,vv=350,as=1"


def test_build_jupiter_time_period_command_validates_time_format() -> None:
    with pytest.raises(ValueError, match="start-time must be"):
        build_command_payload("JPLS-1", "time-period/0/start-time", "25:00")
