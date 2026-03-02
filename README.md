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

1. In integration options, enable `Enable cloud MQTT transport`.
2. The integration auto-generates `/config/marstek_cloudconnect/broker_profiles.json` for `hame-2025` when this file is missing.

No manual folder creation is required if the required files already exist in common Home Assistant/add-on locations.

Required source files are:
   - `hame-2025-url`
   - `ca.crt`
   - `hame-2025.crt`
   - `hame-2025.key`
   - `hame-2025-topic-encryption-key`

If you want to define it manually, you can still copy `broker_profiles.example.json` from this repository.

You can also directly reuse an existing `hame-relay` broker config file (for example `/config/hame-relay/brokers.json`).
The integration supports the same `@file` reference style used there, including `url`, `ca`, `cert`, `key`, and `topic_encryption_key`.
If the configured path is missing, the integration automatically tries these fallback paths:

- `/config/custom_components/marstek_cloudconnect/broker_profiles.json` (bundled template)
- `/config/marstek_cloudconnect/broker_profiles.json`
- `/config/hame-relay/brokers.json`
- `/config/hame_relay/brokers.json`
- `/config/addons_config/hame_relay/brokers.json`

If no profile file exists, the integration then tries to auto-generate a `hame-2025` profile from cert directories in this order:

- `/config/custom_components/marstek_cloudconnect/certs`
- `/config/marstek_cloudconnect/certs`
- `/config/hame-relay/certs`
- `/config/hame_relay/certs`
- `/config/addons_config/hame_relay/certs`

If those direct cert directories do not contain all files, the integration also scans recursively under:

- `/config`
- `/addon_configs`

## HACS Direct Distribution

For direct HACS distribution with bundled cert files, releases are packaged via GitHub Actions.
The workflow `.github/workflows/release-package.yml` injects cert material into
`custom_components/marstek_cloudconnect/certs` during release build and uploads
`marstek_cloudconnect.zip`.

Required repository secrets:

- `CA_CERTIFICATE`
- `CLIENT_CERTIFICATE_2025`
- `CLIENT_KEY_2025`
- `HAME_2025_URL`
- `TOPIC_ENCRYPTION_KEY_2025`

Notes:
- `mailbox` means your app email address.
- Broker username/password is not used for cloud transport.
- Battery power and detailed PV power values are available once transport telemetry is flowing.

## Development Notes

- Integration domain: `marstek_cloudconnect`
- Minimum Home Assistant: `2024.12.0`
- Python package path: `custom_components/marstek_cloudconnect`
