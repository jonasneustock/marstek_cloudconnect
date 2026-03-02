from __future__ import annotations

import json
from pathlib import Path

from custom_components.marstek_cloudconnect.broker_profiles import (
    load_broker_profiles,
    resolve_or_generate_profiles_path,
)


def test_load_broker_profiles_resolves_relative_secret_files(tmp_path) -> None:
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    (cert_dir / "ca.crt").write_text("ca", encoding="utf-8")
    (cert_dir / "hame-2025.crt").write_text("cert", encoding="utf-8")
    (cert_dir / "hame-2025.key").write_text("key", encoding="utf-8")
    (cert_dir / "topic-key").write_text("00112233445566778899aabbccddeeff", encoding="utf-8")

    profiles_file = tmp_path / "broker_profiles.json"
    profiles_file.write_text(
        json.dumps(
            {
                "hame-2025": {
                    "url": "mqtts://example.org:8883",
                    "ca_file": "certs/ca.crt",
                    "cert_file": "certs/hame-2025.crt",
                    "key_file": "certs/hame-2025.key",
                    "topic_prefix": "marstek_energy/",
                    "topic_encryption_key": "@certs/topic-key",
                }
            }
        ),
        encoding="utf-8",
    )

    profiles = load_broker_profiles(str(profiles_file))
    profile = profiles["hame-2025"]

    assert profile.url == "mqtts://example.org:8883"
    assert profile.topic_prefix == "marstek_energy/"
    assert profile.topic_encryption_key == "00112233445566778899aabbccddeeff"
    assert profile.ca_file.endswith("certs/ca.crt")


def test_load_hame_relay_style_profiles_with_at_file_refs(tmp_path) -> None:
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    (cert_dir / "ca.crt").write_text("ca", encoding="utf-8")
    (cert_dir / "hame-2025.crt").write_text("cert", encoding="utf-8")
    (cert_dir / "hame-2025.key").write_text("key", encoding="utf-8")
    (cert_dir / "hame-2025-url").write_text("mqtts://broker.example.org:8883", encoding="utf-8")
    (cert_dir / "hame-2025-topic-key").write_text("00112233445566778899aabbccddeeff", encoding="utf-8")

    profiles_file = tmp_path / "brokers.json"
    profiles_file.write_text(
        json.dumps(
            {
                "hame-2025": {
                    "url": "@certs/hame-2025-url",
                    "ca": "@certs/ca.crt",
                    "cert": "@certs/hame-2025.crt",
                    "key": "@certs/hame-2025.key",
                    "topic_prefix": "marstek_energy/",
                    "topic_encryption_key": "@certs/hame-2025-topic-key",
                }
            }
        ),
        encoding="utf-8",
    )

    profiles = load_broker_profiles(str(profiles_file))
    profile = profiles["hame-2025"]

    assert profile.url == "mqtts://broker.example.org:8883"
    assert profile.ca_file.endswith("certs/ca.crt")
    assert profile.cert_file.endswith("certs/hame-2025.crt")
    assert profile.key_file.endswith("certs/hame-2025.key")
    assert profile.topic_encryption_key == "00112233445566778899aabbccddeeff"


def test_resolve_or_generate_profiles_path_generates_hame_2025_profile(tmp_path) -> None:
    cert_dir = tmp_path / "relay-certs"
    cert_dir.mkdir()
    (cert_dir / "hame-2025-url").write_text("mqtts://generated.example.org:8883", encoding="utf-8")
    (cert_dir / "ca.crt").write_text("ca", encoding="utf-8")
    (cert_dir / "hame-2025.crt").write_text("cert", encoding="utf-8")
    (cert_dir / "hame-2025.key").write_text("key", encoding="utf-8")
    (cert_dir / "hame-2025-topic-encryption-key").write_text(
        "00112233445566778899aabbccddeeff",
        encoding="utf-8",
    )

    generated_path = tmp_path / "marstek_cloudconnect" / "broker_profiles.json"

    result = resolve_or_generate_profiles_path(
        configured_path=str(generated_path),
        fallback_paths=[],
        cert_search_dirs=[str(cert_dir)],
        cert_discovery_roots=[],
    )

    assert result.auto_generated is True
    assert result.generation_source == str(cert_dir)
    assert result.error is None
    assert Path(result.profiles_path).exists()

    payload = json.loads(Path(result.profiles_path).read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"hame-2025"}
    profile = payload["hame-2025"]
    assert profile["url"] == "mqtts://generated.example.org:8883"
    assert profile["ca_file"] == str((cert_dir / "ca.crt").resolve())
    assert profile["cert_file"] == str((cert_dir / "hame-2025.crt").resolve())
    assert profile["key_file"] == str((cert_dir / "hame-2025.key").resolve())
    assert profile["topic_encryption_key"] == "00112233445566778899aabbccddeeff"


def test_resolve_or_generate_profiles_path_returns_error_when_required_files_missing(tmp_path) -> None:
    cert_dir = tmp_path / "empty-certs"
    cert_dir.mkdir()
    configured = tmp_path / "missing" / "broker_profiles.json"

    result = resolve_or_generate_profiles_path(
        configured_path=str(configured),
        fallback_paths=[],
        cert_search_dirs=[str(cert_dir)],
        cert_discovery_roots=[],
    )

    assert result.auto_generated is False
    assert result.error is not None
    assert "Required files: hame-2025-url" in result.error
    assert result.profiles_path == str(configured)


def test_resolve_or_generate_profiles_path_discovers_files_recursively(tmp_path) -> None:
    search_root = tmp_path / "config"
    nested = search_root / "addons_config" / "hame_relay" / "certs"
    nested.mkdir(parents=True)

    (nested / "hame-2025-url").write_text("mqtts://recursive.example.org:8883", encoding="utf-8")
    (nested / "ca.crt").write_text("ca", encoding="utf-8")
    (nested / "hame-2025.crt").write_text("cert", encoding="utf-8")
    (nested / "hame-2025.key").write_text("key", encoding="utf-8")
    (nested / "hame-2025-topic-encryption-key").write_text(
        "00112233445566778899aabbccddeeff",
        encoding="utf-8",
    )

    generated_path = tmp_path / "marstek_cloudconnect" / "broker_profiles.json"
    result = resolve_or_generate_profiles_path(
        configured_path=str(generated_path),
        fallback_paths=[],
        cert_search_dirs=[],
        cert_discovery_roots=[str(search_root)],
    )

    assert result.auto_generated is True
    assert result.error is None
    payload = json.loads(Path(result.profiles_path).read_text(encoding="utf-8"))
    assert payload["hame-2025"]["url"] == "mqtts://recursive.example.org:8883"
