from __future__ import annotations

import json

from custom_components.marstek_cloudconnect.broker_profiles import load_broker_profiles


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
