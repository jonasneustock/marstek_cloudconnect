from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence

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


@dataclass(frozen=True, slots=True)
class ProfilesBootstrapResult:
    profiles_path: str
    auto_generated: bool
    generation_source: str | None
    error: str | None


def resolve_or_generate_profiles_path(
    configured_path: str,
    fallback_paths: Sequence[str],
    cert_search_dirs: Sequence[str],
    cert_discovery_roots: Sequence[str],
) -> ProfilesBootstrapResult:
    candidates = _unique_paths([configured_path, *fallback_paths])
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return ProfilesBootstrapResult(
                profiles_path=str(path),
                auto_generated=False,
                generation_source=None,
                error=None,
            )

    unique_cert_dirs = _unique_paths(list(cert_search_dirs))

    generated = _try_generate_hame2025_profile_file(
        configured_path,
        unique_cert_dirs,
        cert_discovery_roots,
    )
    if generated is not None:
        generated_path, source = generated
        return ProfilesBootstrapResult(
            profiles_path=generated_path,
            auto_generated=True,
            generation_source=source,
            error=None,
        )

    return ProfilesBootstrapResult(
        profiles_path=configured_path,
        auto_generated=False,
        generation_source=None,
        error=_build_generation_error(
            configured_path,
            unique_cert_dirs,
            cert_discovery_roots,
        ),
    )


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


def _try_generate_hame2025_profile_file(
    configured_path: str,
    cert_search_dirs: Sequence[str],
    cert_discovery_roots: Sequence[str],
) -> tuple[str, str] | None:
    cert_files = {
        "url": "hame-2025-url",
        "ca_file": "ca.crt",
        "cert_file": "hame-2025.crt",
        "key_file": "hame-2025.key",
        "topic_encryption_key": "hame-2025-topic-encryption-key",
    }

    for cert_root in cert_search_dirs:
        cert_dir = Path(cert_root).expanduser()
        if not cert_dir.exists() or not cert_dir.is_dir():
            continue

        resolved = _resolve_cert_files_from_directory(cert_dir, cert_files)
        if resolved is None:
            continue

        generated = _write_generated_profile(configured_path, resolved)
        if generated is not None:
            output_path, _ = generated
            return output_path, str(cert_dir)

    discovered = _discover_cert_files(cert_files, cert_discovery_roots)
    if discovered is not None:
        generated = _write_generated_profile(configured_path, discovered)
        if generated is not None:
            output_path, source = generated
            return output_path, source

    return None


def _resolve_cert_files_from_directory(
    cert_dir: Path,
    cert_files: dict[str, str],
) -> dict[str, Path] | None:
    resolved = {key: cert_dir / file_name for key, file_name in cert_files.items()}
    if any(not path.is_file() for path in resolved.values()):
        return None
    return resolved


def _discover_cert_files(
    cert_files: dict[str, str],
    cert_discovery_roots: Sequence[str],
) -> dict[str, Path] | None:
    resolved: dict[str, Path] = {}

    for root_str in cert_discovery_roots:
        root = Path(root_str).expanduser()
        if not root.exists() or not root.is_dir():
            continue

        for key, file_name in cert_files.items():
            if key in resolved:
                continue
            found = _find_first_file(root, file_name)
            if found is not None:
                resolved[key] = found

        if len(resolved) == len(cert_files):
            return resolved

    return None


def _find_first_file(root: Path, file_name: str) -> Path | None:
    for candidate in root.rglob(file_name):
        if candidate.is_file():
            return candidate
    return None


def _write_generated_profile(
    configured_path: str,
    resolved: dict[str, Path],
) -> tuple[str, str] | None:
    try:
        url_value = resolved["url"].read_text(encoding="utf-8").strip()
        topic_key_value = resolved["topic_encryption_key"].read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not url_value or not topic_key_value:
        return None

    profile_payload = {
        "hame-2025": {
            "url": url_value,
            "ca_file": str(resolved["ca_file"].resolve()),
            "cert_file": str(resolved["cert_file"].resolve()),
            "key_file": str(resolved["key_file"].resolve()),
            "topic_prefix": "marstek_energy/",
            "client_id_prefix": "mst_",
            "topic_encryption_key": topic_key_value,
        }
    }

    output_path = Path(configured_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile_payload, indent=2) + "\n", encoding="utf-8")

    source = str(Path(resolved["ca_file"]).parent)
    return str(output_path), source


def _build_generation_error(
    configured_path: str,
    cert_search_dirs: Sequence[str],
    cert_discovery_roots: Sequence[str],
) -> str:
    checked = ", ".join(cert_search_dirs)
    discovery = ", ".join(cert_discovery_roots)
    return (
        f"Broker profiles file not found: {configured_path}. "
        "Auto-generation requires hame-2025 files in one of these directories: "
        f"{checked}. It also scans recursively in: {discovery}. "
        "Required files: hame-2025-url, ca.crt, hame-2025.crt, hame-2025.key, "
        "hame-2025-topic-encryption-key."
    )


def _unique_paths(paths: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique
