from __future__ import annotations

import asyncio
import logging
from typing import Callable

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant

from .const import CONF_BROKER_PASSWORD, CONF_BROKER_URL, CONF_BROKER_USERNAME
from .models import CloudDevice

_LOGGER = logging.getLogger(__name__)

TransportCallback = Callable[[str, str], None]


class MarstekCloudTransport:
    def __init__(
        self,
        hass: HomeAssistant,
        options: dict,
        on_message: TransportCallback,
    ) -> None:
        self._hass = hass
        self._options = options
        self._on_message_cb = on_message
        self._device_by_remote_id: dict[str, CloudDevice] = {}
        self._client: mqtt.Client | None = None
        self._started = False

    async def async_start(self, devices: list[CloudDevice]) -> None:
        self._device_by_remote_id = {device.remote_id: device for device in devices if device.remote_id}
        if not self._device_by_remote_id:
            _LOGGER.debug("Transport start skipped, no devices with remote IDs")
            return

        await self._hass.async_add_executor_job(self._sync_start)

    async def async_stop(self) -> None:
        await self._hass.async_add_executor_job(self._sync_stop)

    async def async_publish_command(self, device: CloudDevice, payload: str) -> None:
        if not self._started or not self._client:
            raise RuntimeError("Transport is not connected")
        topic = self.build_app_topic(device)
        await self._hass.async_add_executor_job(self._client.publish, topic, payload, 1, False)

    def build_device_topic(self, device: CloudDevice) -> str:
        return f"{device.topic_prefix}{device.device_type}/device/{device.remote_id}/ctrl"

    def build_app_topic(self, device: CloudDevice) -> str:
        return f"{device.topic_prefix}{device.device_type}/App/{device.remote_id}/ctrl"

    def _sync_start(self) -> None:
        if self._started:
            return

        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        username = self._options.get(CONF_BROKER_USERNAME)
        password = self._options.get(CONF_BROKER_PASSWORD)
        if username:
            client.username_pw_set(username=username, password=password)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        host, port, use_tls = _parse_url(self._options[CONF_BROKER_URL])
        if use_tls:
            client.tls_set()

        client.connect(host=host, port=port, keepalive=30)
        client.loop_start()
        self._client = client
        self._started = True

    def _sync_stop(self) -> None:
        if not self._client:
            self._started = False
            return

        self._client.loop_stop()
        self._client.disconnect()
        self._client = None
        self._started = False

    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            _LOGGER.warning("MQTT connect failed: %s", reason_code)
            return

        for device in self._device_by_remote_id.values():
            topic = self.build_device_topic(device)
            client.subscribe(topic, qos=1)
        _LOGGER.info("Cloud transport connected and subscribed for %s devices", len(self._device_by_remote_id))

    def _on_disconnect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        _LOGGER.warning("Cloud transport disconnected: %s", reason_code)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = msg.payload.decode("utf-8", errors="replace")
            self._hass.loop.call_soon_threadsafe(self._on_message_cb, msg.topic, payload)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.debug("Failed to process MQTT message: %s", err)


def _parse_url(url: str) -> tuple[str, int, bool]:
    normalized = url.strip()
    use_tls = normalized.startswith("mqtts://")
    without_proto = normalized.split("://", maxsplit=1)[-1]
    host_part = without_proto.split("/", maxsplit=1)[0]
    if ":" in host_part:
        host, port_raw = host_part.rsplit(":", maxsplit=1)
        return host, int(port_raw), use_tls
    return host_part, (8883 if use_tls else 1883), use_tls
