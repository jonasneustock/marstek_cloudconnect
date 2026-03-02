from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Sequence

from aiohttp import ClientError, ClientSession

from .brokers import pick_profile
from .models import CloudDevice
from .topic_crypto import calculate_remote_id_cq, extract_first_salt, supports_cq

_LOGGER = logging.getLogger(__name__)


class MarstekApiError(Exception):
    """Raised for API-level errors."""


class MarstekAuthError(MarstekApiError):
    """Raised when credentials are invalid."""


class MarstekApiClient:
    def __init__(self, session: ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def fetch_devices(self, mailbox: str, password: str) -> list[CloudDevice]:
        token_payload = await self._request_with_retry(
            self._fetch_device_token, mailbox, password, operation_name="fetch token"
        )
        token = token_payload.get("token")
        if not token:
            raise MarstekApiError("Token missing from API response")

        list_payload = await self._request_with_retry(
            self._fetch_device_list, mailbox, token, operation_name="fetch devices"
        )
        raw_devices = list_payload.get("data", [])

        devices: list[CloudDevice] = []
        for raw in raw_devices:
            version_raw = raw.get("version")
            version_num: int | None
            try:
                version_num = int(version_raw) if version_raw is not None else None
            except (TypeError, ValueError):
                version_num = None

            device_id = str(raw.get("devid", "")).strip()
            mac = str(raw.get("mac", "")).replace(":", "").strip().lower()
            device_type = str(raw.get("type", "")).strip().upper()
            name = str(raw.get("name", device_id)).strip() or device_id
            salt = raw.get("salt")

            salt_for_cq = extract_first_salt(salt)
            can_use_cq = supports_cq(device_type, str(version_raw) if version_raw is not None else None)
            remote_id = device_id
            if can_use_cq and salt_for_cq:
                try:
                    remote_id = calculate_remote_id_cq(salt_for_cq, mac, device_type)
                except Exception as err:  # pragma: no cover - defensive fallback
                    _LOGGER.debug("Failed to calculate cq remote id for %s: %s", device_id, err)

            profile = pick_profile(device_type, version_num)

            devices.append(
                CloudDevice(
                    device_id=device_id,
                    mac=mac,
                    device_type=device_type,
                    name=name,
                    version_raw=str(version_raw) if version_raw is not None else None,
                    version=version_num,
                    salt=salt,
                    remote_id=remote_id,
                    supports_cq=can_use_cq,
                    broker_id=profile.broker_id,
                    topic_prefix=profile.topic_prefix,
                )
            )

        return devices

    async def _request_with_retry(self, func, *args, operation_name: str):
        errors: list[Exception] = []
        for attempt in range(1, 4):
            try:
                return await func(*args)
            except (MarstekAuthError, MarstekApiError):
                raise
            except (ClientError, TimeoutError) as err:
                errors.append(err)
                if attempt < 3:
                    wait_seconds = 2 ** (attempt - 1)
                    _LOGGER.debug("%s attempt %s failed, retrying in %ss", operation_name, attempt, wait_seconds)
                    await asyncio.sleep(wait_seconds)
                else:
                    raise MarstekApiError(f"{operation_name} failed: {err}") from err

        raise MarstekApiError(f"{operation_name} failed: {errors[-1]}")

    async def _fetch_device_token(self, mailbox: str, password: str) -> dict:
        pwd_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
        url = f"{self._base_url}/app/Solar/v2_get_device.php"
        params = {"mailbox": mailbox, "pwd": pwd_hash}

        async with self._session.get(url, params=params) as response:
            response.raise_for_status()
            payload = await response.json()

        code = payload.get("code")
        if code == "4":
            raise MarstekAuthError("Incorrect mailbox or password")
        if code != "2":
            raise MarstekApiError(f"Unexpected token response code: {code} ({payload.get('msg')})")
        return payload

    async def _fetch_device_list(self, mailbox: str, token: str) -> dict:
        url = f"{self._base_url}/ems/api/v1/getDeviceList"
        params = {"mailbox": mailbox, "token": token}

        async with self._session.get(url, params=params) as response:
            response.raise_for_status()
            payload = await response.json()

        code = payload.get("code")
        if code != 1:
            raise MarstekApiError(f"Unexpected device list response code: {code} ({payload.get('msg')})")
        data = payload.get("data")
        if not isinstance(data, Sequence):
            raise MarstekApiError("Device list payload has invalid data field")
        return payload
