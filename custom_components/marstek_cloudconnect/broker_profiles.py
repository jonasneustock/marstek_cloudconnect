from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .brokers import default_client_id_prefix_for_broker, default_topic_prefix_for_broker


class BrokerProfilesError(Exception):
    """Raised when broker profile configuration is invalid."""


@dataclass(frozen=True, slots=True)
class BrokerConnectionProfile:
    broker_id: str
    url: str
    ca_file: str
    cert_file: str
    key_file: str
    topic_prefix: str
    client_id_prefix: str
    topic_encryption_key: str | None = None


def load_broker_profiles(file_path: str) -> dict[str, BrokerConnectionProfile]:
    path = Path(file_path).expanduser()
    if not path.exists():
        raise BrokerProfilesError(f"Broker profiles file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        payload = json.loads(content)
    except (OSError, json.JSONDecodeError) as err:
        raise BrokerProfilesError(f"Failed to read broker profiles file: {path}") from err

    if not isinstance(payload, dict):
        raise BrokerProfilesError("Broker profiles file must contain a JSON object")

    raw_profiles = payload.get("brokers", payload)
    if not isinstance(raw_profiles, dict):
        raise BrokerProfilesError("Broker profiles must be a JSON object")

    base_dir = path.parent
    profiles: dict[str, BrokerConnectionProfile] = {}
    for broker_id, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            raise BrokerProfilesError(f"Broker profile '{broker_id}' must be an object")

        url = _resolve_string_value(raw, "url", broker_id, base_dir)
        ca_file = _resolve_secret_file(raw, broker_id, base_dir, "ca_file", "ca")
        cert_file = _resolve_secret_file(raw, broker_id, base_dir, "cert_file", "cert")
        key_file = _resolve_secret_file(raw, broker_id, base_dir, "key_file", "key")

        topic_prefix = _read_optional_str(raw, "topic_prefix") or default_topic_prefix_for_broker(broker_id)
        client_id_prefix = _read_optional_str(raw, "client_id_prefix") or default_client_id_prefix_for_broker(
            broker_id
        )

        topic_key = _read_optional_str(raw, "topic_encryption_key")
        if topic_key is not None:
            topic_key = _resolve_inline_file_reference(
                topic_key,
                base_dir,
                broker_id,
                "topic_encryption_key",
            )

        profiles[broker_id] = BrokerConnectionProfile(
            broker_id=broker_id,
            url=url,
            ca_file=str(ca_file),
            cert_file=str(cert_file),
            key_file=str(key_file),
            topic_prefix=topic_prefix,
            client_id_prefix=client_id_prefix,
            topic_encryption_key=topic_key,
        )

    return profiles


def _resolve_secret_file(
    raw: dict,
    broker_id: str,
    base_dir: Path,
    file_key: str,
    fallback_key: str,
) -> Path:
    file_value = _read_optional_str(raw, file_key)
    if file_value:
        path = _resolve_path(base_dir, file_value[1:] if file_value.startswith("@") else file_value)
    else:
        legacy_value = _read_optional_str(raw, fallback_key)
        if not legacy_value:
            raise BrokerProfilesError(
                f"Broker profile '{broker_id}' must define '{file_key}' or legacy '{fallback_key}'"
            )
        path = _resolve_path(base_dir, legacy_value[1:] if legacy_value.startswith("@") else legacy_value)

    if not path.exists() or not path.is_file():
        raise BrokerProfilesError(f"Broker profile '{broker_id}' file does not exist: {path}")

    return path


def _resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return base_dir / path


def _expect_str(raw: dict, key: str, broker_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BrokerProfilesError(f"Broker profile '{broker_id}' is missing '{key}'")
    return value.strip()


def _resolve_string_value(raw: dict, key: str, broker_id: str, base_dir: Path) -> str:
    value = _expect_str(raw, key, broker_id)
    return _resolve_inline_file_reference(value, base_dir, broker_id, key)


def _resolve_inline_file_reference(value: str, base_dir: Path, broker_id: str, field_name: str) -> str:
    if not value.startswith("@"):
        return value

    file_path = _resolve_path(base_dir, value[1:])
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except OSError as err:
        raise BrokerProfilesError(
            f"Broker profile '{broker_id}' field '{field_name}' could not load referenced file: {file_path}"
        ) from err


def _read_optional_str(raw: dict, key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
