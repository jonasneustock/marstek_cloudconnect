# Marstek Cloud Connect

Home Assistant custom integration for Marstek/Hame cloud-connected devices.

## Acknowledgements

Huge thanks to [tomquist](https://github.com/tomquist) for the original `hm2mqtt` and `hame-relay` work that made this integration possible.
This repository continuously migrates that work into a native Home Assistant integration whenever feasible, while preserving protocol behavior and compatibility.

## Status

This repository currently contains:

- `hm2mqtt/`: TypeScript parsing and device mapping logic.
- `hame-relay/`: TypeScript cloud relay logic and topic helpers.
- `custom_components/marstek_cloudconnect/`: new Home Assistant integration (HACS-first).

The first integration release focuses on:

- Home Assistant config flow for cloud credentials.
- Device discovery through Hame API.
- Native Home Assistant entities for discovered devices, telemetry, and core controls.
- Foundations for protocol compatibility (broker routing, remote topic ID helper, parser parity, and command builders).

## HACS Installation

1. In HACS, open the custom repositories menu.
2. Add this repository URL.
3. Select category `Integration`.
4. Install `Marstek Cloud Connect`.
5. Restart Home Assistant.
6. Go to Settings -> Devices & Services -> Add Integration.
7. Search for `Marstek Cloud Connect`.

## Cloud Transport Setup (mTLS)

The integration now supports the real Hame cloud broker flow with certificate-based authentication.

1. Create directory `/config/marstek_cloudconnect/certs` in your Home Assistant host.
2. Place your broker certificates and keys there (do not commit them to git).
3. Create `/config/marstek_cloudconnect/broker_profiles.json` like this:

```json
{
  "hame-2024": {
    "url": "mqtts://<hame-2024-host>:8883",
    "ca_file": "/config/marstek_cloudconnect/certs/ca.crt",
    "cert_file": "/config/marstek_cloudconnect/certs/hame-2024.crt",
    "key_file": "/config/marstek_cloudconnect/certs/hame-2024.key",
    "topic_prefix": "hame_energy/",
    "client_id_prefix": "hm_"
  },
  "hame-2025": {
    "url": "mqtts://<hame-2025-host>:8883",
    "ca_file": "/config/marstek_cloudconnect/certs/ca.crt",
    "cert_file": "/config/marstek_cloudconnect/certs/hame-2025.crt",
    "key_file": "/config/marstek_cloudconnect/certs/hame-2025.key",
    "topic_prefix": "marstek_energy/",
    "client_id_prefix": "mst_",
    "topic_encryption_key": "<hex-key>"
  }
}
```

If you want the exact `hame-relay` baseline for `hame-2025`, copy `broker_profiles.example.json` from this repository to `/config/marstek_cloudconnect/broker_profiles.json` and then add your cert/key/url files.

4. In integration options, enable `Enable cloud MQTT transport`.
5. Keep `Broker profiles path` set to `/config/marstek_cloudconnect/broker_profiles.json` unless you use a custom path.

You can also directly reuse an existing `hame-relay` broker config file (for example `/config/hame-relay/brokers.json`).
The integration supports the same `@file` reference style used there, including `url`, `ca`, `cert`, `key`, and `topic_encryption_key`.
If the configured path is missing, the integration automatically tries these fallback paths:

- `/config/marstek_cloudconnect/broker_profiles.json`
- `/config/hame-relay/brokers.json`
- `/config/hame_relay/brokers.json`
- `/config/addons_config/hame_relay/brokers.json`

Notes:
- `mailbox` means your app email address.
- Broker username/password is not used for cloud transport.
- Battery power and detailed PV power values are available once transport telemetry is flowing.

## Development Notes

- Integration domain: `marstek_cloudconnect`
- Minimum Home Assistant: `2024.12.0`
- Python package path: `custom_components/marstek_cloudconnect`
