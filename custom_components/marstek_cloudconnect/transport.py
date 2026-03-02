from __future__ import annotations

import logging
from secrets import token_hex
from typing import Any, Callable

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant

from .broker_profiles import BrokerConnectionProfile, BrokerProfilesError, load_broker_profiles
from .models import CloudDevice
from .topic_crypto import calculate_remote_id_aes

_LOGGER = logging.getLogger(__name__)

TransportCallback = Callable[[str, str], None]


class MarstekCloudTransport:
    def __init__(
        self,
        hass: HomeAssistant,
        on_message: TransportCallback,
    ) -> None:
        self._hass = hass
        self._on_message_cb = on_message
        self._profiles: dict[str, BrokerConnectionProfile] = {}
        self._devices_by_broker: dict[str, list[CloudDevice]] = {}
        self._clients: dict[str, mqtt.Client] = {}
        self._connected_brokers: set[str] = set()
        self._started = False

    async def async_start(self, devices: list[CloudDevice], profiles_path: str) -> None:
        await self._hass.async_add_executor_job(self._sync_start, devices, profiles_path)

    async def async_stop(self) -> None:
        await self._hass.async_add_executor_job(self._sync_stop)

    async def async_publish_command(self, device: CloudDevice, payload: str) -> None:
        if not self._started:
            raise RuntimeError("Transport is not started")

        broker_id = device.broker_id
        if not broker_id:
            raise RuntimeError(f"Device {device.device_id} has no broker ID")

        client = self._clients.get(broker_id)
        if client is None:
            raise RuntimeError(f"No MQTT client configured for broker '{broker_id}'")

        topic = self.build_app_topic(device)
        info: mqtt.MQTTMessageInfo = await self._hass.async_add_executor_job(client.publish, topic, payload, 1, False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Failed to publish MQTT payload, rc={info.rc}")

    def build_device_topic(self, device: CloudDevice) -> str:
        return f"{device.topic_prefix}{device.device_type}/device/{device.remote_id}/ctrl"

    def build_app_topic(self, device: CloudDevice) -> str:
        return f"{device.topic_prefix}{device.device_type}/App/{device.remote_id}/ctrl"

    def _sync_start(self, devices: list[CloudDevice], profiles_path: str) -> None:
        profiles = load_broker_profiles(profiles_path)
        devices_by_broker = self._group_devices_by_broker(devices, profiles)

        desired_brokers = set(devices_by_broker)
        for broker_id in list(self._clients):
            if broker_id not in desired_brokers:
                self._disconnect_client(broker_id)

        self._profiles = profiles
        self._devices_by_broker = devices_by_broker

        for broker_id in desired_brokers:
            if broker_id not in self._clients:
                self._clients[broker_id] = self._create_client(self._profiles[broker_id])
            if broker_id in self._connected_brokers:
                self._subscribe_device_topics(broker_id)

        self._started = bool(self._clients)

    def _sync_stop(self) -> None:
        for broker_id in list(self._clients):
            self._disconnect_client(broker_id)
        self._profiles = {}
        self._devices_by_broker = {}
        self._connected_brokers = set()
        self._started = False

    def _group_devices_by_broker(
        self,
        devices: list[CloudDevice],
        profiles: dict[str, BrokerConnectionProfile],
    ) -> dict[str, list[CloudDevice]]:
        grouped: dict[str, list[CloudDevice]] = {}

        for device in devices:
            broker_id = device.broker_id
            if not broker_id:
                _LOGGER.debug("Skipping device %s because broker_id is missing", device.device_id)
                continue

            profile = profiles.get(broker_id)
            if profile is None:
                _LOGGER.warning(
                    "Skipping device %s because broker profile '%s' is missing",
                    device.device_id,
                    broker_id,
                )
                continue

            device.topic_prefix = profile.topic_prefix
            if (
                profile.topic_encryption_key
                and not device.supports_cq
                and device.remote_id == device.device_id
                and device.mac
            ):
                try:
                    device.remote_id = calculate_remote_id_aes(profile.topic_encryption_key, device.mac)
                except ValueError as err:
                    _LOGGER.warning(
                        "Failed AES topic-id calculation for %s on %s: %s",
                        device.device_id,
                        broker_id,
                        err,
                    )

            grouped.setdefault(broker_id, []).append(device)

        return grouped

    def _create_client(self, profile: BrokerConnectionProfile) -> mqtt.Client:
        client_id = f"{profile.client_id_prefix}{token_hex(12)}"
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        client.user_data_set({"broker_id": profile.broker_id})
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        client.reconnect_delay_set(min_delay=1, max_delay=120)

        host, port, use_tls = _parse_url(profile.url)
        if not use_tls:
            raise BrokerProfilesError(f"Broker profile '{profile.broker_id}' URL must use mqtts://")

        client.tls_set(
            ca_certs=profile.ca_file,
            certfile=profile.cert_file,
            keyfile=profile.key_file,
        )
        client.connect_async(host=host, port=port, keepalive=30)
        client.loop_start()

        _LOGGER.info("Started MQTT client for broker %s (%s:%s)", profile.broker_id, host, port)
        return client

    def _disconnect_client(self, broker_id: str) -> None:
        client = self._clients.pop(broker_id, None)
        if client is None:
            return
        self._connected_brokers.discard(broker_id)
        try:
            client.loop_stop()
            client.disconnect()
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.debug("Error while disconnecting MQTT client for %s: %s", broker_id, err)

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        broker_id = _broker_id_from_userdata(userdata)
        reason = _reason_code_to_int(reason_code)
        if broker_id is None:
            _LOGGER.warning("MQTT connected without broker context")
            return
        if reason != 0:
            _LOGGER.warning("MQTT connect failed for %s: %s", broker_id, reason_code)
            return

        self._connected_brokers.add(broker_id)
        self._subscribe_device_topics(broker_id)

    def _subscribe_device_topics(self, broker_id: str) -> None:
        client = self._clients.get(broker_id)
        devices = self._devices_by_broker.get(broker_id, [])
        if client is None or not devices:
            return

        topics = [(self.build_device_topic(device), 1) for device in devices]
        client.subscribe(topics)
        _LOGGER.info("Subscribed %s topics for broker %s", len(topics), broker_id)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        broker_id = _broker_id_from_userdata(userdata)
        if broker_id is None:
            _LOGGER.warning("MQTT disconnected without broker context")
            return

        self._connected_brokers.discard(broker_id)
        _LOGGER.warning("MQTT disconnected for broker %s: %s", broker_id, reason_code)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
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


def _broker_id_from_userdata(userdata: Any) -> str | None:
    if isinstance(userdata, dict):
        broker_id = userdata.get("broker_id")
        if isinstance(broker_id, str):
            return broker_id
    return None


def _reason_code_to_int(reason_code: Any) -> int:
    if isinstance(reason_code, int):
        return reason_code
    try:
        return int(reason_code)
    except (TypeError, ValueError):
        return -1
