from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrokerProfile:
    broker_id: str
    topic_prefix: str
    client_id_prefix: str
    min_versions: dict[str, int]


BROKER_PROFILES: tuple[BrokerProfile, ...] = (
    BrokerProfile(
        broker_id="hame-2024",
        topic_prefix="hame_energy/",
        client_id_prefix="hm_",
        min_versions={
            "HMA": 0,
            "HMB": 0,
            "HMF": 0,
            "HMJ": 0,
            "HMG": 0,
            "HMM": 0,
            "HMN": 0,
            "JPLS": 0,
        },
    ),
    BrokerProfile(
        broker_id="hame-2025",
        topic_prefix="marstek_energy/",
        client_id_prefix="mst_",
        min_versions={
            "HMA": 226,
            "HMF": 226,
            "HMI": 120,
            "HMJ": 108,
            "HMK": 226,
            "HMG": 153,
            "HMM": 135,
            "HMN": 135,
            "JPLS": 135,
            "VNSE3": 0,
            "VNSA": 0,
            "VNSD": 0,
        },
    ),
)


def pick_profile(device_type: str, version: int | None) -> BrokerProfile:
    if version is None:
        return BROKER_PROFILES[1]

    base = device_type.split("-", maxsplit=1)[0].upper()
    selected = BROKER_PROFILES[0]
    selected_min = -1
    for profile in BROKER_PROFILES:
        min_required = profile.min_versions.get(base)
        if min_required is None:
            continue
        if version >= min_required and min_required > selected_min:
            selected = profile
            selected_min = min_required
    return selected


def get_broker_profile(broker_id: str) -> BrokerProfile | None:
    for profile in BROKER_PROFILES:
        if profile.broker_id == broker_id:
            return profile
    return None


def default_topic_prefix_for_broker(broker_id: str) -> str:
    profile = get_broker_profile(broker_id)
    if profile is None:
        return "marstek_energy/"
    return profile.topic_prefix


def default_client_id_prefix_for_broker(broker_id: str) -> str:
    profile = get_broker_profile(broker_id)
    if profile is None:
        return "hm_"
    return profile.client_id_prefix
