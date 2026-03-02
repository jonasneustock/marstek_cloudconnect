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

## Development Notes

- Integration domain: `marstek_cloudconnect`
- Minimum Home Assistant: `2024.12.0`
- Python package path: `custom_components/marstek_cloudconnect`
