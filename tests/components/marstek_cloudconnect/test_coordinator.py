from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.marstek_cloudconnect.coordinator import MarstekCoordinator
from custom_components.marstek_cloudconnect.models import CloudDevice


class _FakeTransport:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def async_publish_command(self, device: CloudDevice, payload: str) -> None:
        self.published.append((device.device_id, payload))


def _build_coordinator_with_device(device: CloudDevice) -> MarstekCoordinator:
    coordinator = MarstekCoordinator.__new__(MarstekCoordinator)
    coordinator.data = {device.device_id: device}
    coordinator.transport = _FakeTransport()

    def _set_data(data):
        coordinator.data = data

    coordinator.async_set_updated_data = _set_data
    return coordinator


def test_handle_transport_message_updates_device_state() -> None:
    device = CloudDevice(
        device_id="dev1",
        mac="001122334455",
        device_type="JPLS-1",
        name="Jupiter",
        version_raw="140",
        version=140,
        salt=None,
        remote_id="remote123",
        supports_cq=True,
    )
    device.topic_prefix = "marstek_energy/"

    coordinator = _build_coordinator_with_device(device)
    topic = "marstek_energy/JPLS-1/device/remote123/ctrl"
    payload = (
        "ele_d=349,ele_m=2193,ele_y=0,pv1_p=94,pv2_p=77,pv3_p=41,pv4_p=60,"
        "grd_d=285,grd_m=2018,grd_o=250,cel_s=2,cel_p=424,cel_c=83,err_t=0,"
        "wor_m=1,wif_s=75,ful_d=1,dod=88,ala_c=0,tim_0=12|0|23|59|127|800|1"
    )

    coordinator.handle_transport_message(topic, payload)

    bms_payload = "b_vol=5252,b_cur=63"
    coordinator.handle_transport_message(topic, bms_payload)

    assert device.available is True
    assert device.telemetry["daily_charging_capacity"] == pytest.approx(3.49)
    assert device.telemetry["combined_power"] == 250
    assert device.telemetry["time_periods"][0]["start_time"] == "12:00"
    assert device.telemetry["solar_total_power"] == 272
    assert device.telemetry["battery_voltage"] == pytest.approx(52.52)
    assert device.telemetry["battery_current"] == pytest.approx(6.3)
    assert device.telemetry["battery_power"] == pytest.approx(330.88)


@pytest.mark.asyncio
async def test_async_send_command_publishes_time_period_payload() -> None:
    device = CloudDevice(
        device_id="dev1",
        mac="001122334455",
        device_type="JPLS-1",
        name="Jupiter",
        version_raw="140",
        version=140,
        salt=None,
        remote_id="remote123",
        supports_cq=True,
    )
    device.telemetry = {
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

    coordinator = _build_coordinator_with_device(device)

    await coordinator.async_send_command("dev1", "time-period/0/power", 350)

    assert coordinator.transport.published == [
        ("dev1", "cd=3,md=2,nm=0,bt=12:00,et=23:59,wk=127,vv=350,as=1")
    ]
    assert device.telemetry["time_periods"][0]["power"] == 350
