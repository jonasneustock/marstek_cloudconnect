from __future__ import annotations

from datetime import timedelta

DOMAIN = "marstek_cloudconnect"

PLATFORMS = ["sensor", "binary_sensor", "button", "number", "select", "switch"]

CONF_MAILBOX = "mailbox"
CONF_BASE_URL = "base_url"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_TRANSPORT = "enable_transport"
CONF_PROFILES_PATH = "profiles_path"

DEFAULT_BASE_URL = "https://eu.hamedata.com"
DEFAULT_SCAN_INTERVAL = 120
DEFAULT_PROFILES_PATH = "/config/marstek_cloudconnect/broker_profiles.json"
LEGACY_PROFILES_PATHS = (
    "/config/hame-relay/brokers.json",
    "/config/hame_relay/brokers.json",
    "/config/addons_config/hame_relay/brokers.json",
)
HAME2025_CERT_SEARCH_DIRS = (
    "/config/custom_components/marstek_cloudconnect/certs",
    "/config/marstek_cloudconnect/certs",
    "/config/hame-relay/certs",
    "/config/hame_relay/certs",
    "/config/addons_config/hame_relay/certs",
)
HAME2025_CERT_DISCOVERY_ROOTS = (
    "/config",
    "/addon_configs",
)
MIN_SCAN_INTERVAL = 30
BMS_POLL_INTERVAL_SECONDS = 60

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SERVICE_REFRESH = "refresh"
SERVICE_SEND_COMMAND = "send_command"

ATTR_DEVICE_ID = "device_id"
