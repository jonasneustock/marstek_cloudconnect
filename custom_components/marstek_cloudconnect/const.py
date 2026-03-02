from __future__ import annotations

from datetime import timedelta

DOMAIN = "marstek_cloudconnect"

PLATFORMS = ["sensor", "binary_sensor", "button", "number", "select", "switch"]

CONF_MAILBOX = "mailbox"
CONF_BASE_URL = "base_url"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_TRANSPORT = "enable_transport"
CONF_BROKER_URL = "broker_url"
CONF_BROKER_USERNAME = "broker_username"
CONF_BROKER_PASSWORD = "broker_password"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_TLS_CA = "tls_ca"
CONF_TLS_CERT = "tls_cert"
CONF_TLS_KEY = "tls_key"
CONF_TLS_INSECURE = "tls_insecure"

DEFAULT_BASE_URL = "https://eu.hamedata.com"
DEFAULT_SCAN_INTERVAL = 120
DEFAULT_BROKER_URL = "mqtts://eu.hamedata.com:8883"
DEFAULT_TOPIC_PREFIX = "marstek_energy/"
MIN_SCAN_INTERVAL = 30

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SERVICE_REFRESH = "refresh"
SERVICE_SEND_COMMAND = "send_command"

ATTR_DEVICE_ID = "device_id"
