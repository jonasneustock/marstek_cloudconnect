from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class CloudDevice:
    device_id: str
    mac: str
    device_type: str
    name: str
    version_raw: str | None
    version: int | None
    salt: str | None
    remote_id: str
    supports_cq: bool
    broker_id: str | None = None
    topic_prefix: str = "marstek_energy/"
    telemetry: dict[str, object] = field(default_factory=dict)
    raw_values: dict[str, str] = field(default_factory=dict)
    last_payload: str | None = None
    last_topic: str | None = None
    last_update: datetime | None = None
    available: bool = False

    def mark_message(self, *, topic: str, payload: str) -> None:
        self.last_topic = topic
        self.last_payload = payload
        self.last_update = _utcnow()
        self.available = True
