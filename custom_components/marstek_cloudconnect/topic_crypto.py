from __future__ import annotations

import hashlib


def extract_first_salt(salt_pair: str | None) -> str:
    if not salt_pair:
        return ""
    return salt_pair.split(",", maxsplit=1)[0].strip()


def supports_cq(vid: str, firmware_version: str | None) -> bool:
    if not vid or not firmware_version:
        return False

    try:
        version = float(firmware_version)
    except ValueError:
        return False

    normalized = vid.upper()

    if any(normalized.startswith(prefix) for prefix in ("JPLS", "HMM", "HMN")):
        return version >= 136.0
    if any(normalized.startswith(prefix) for prefix in ("HMB", "HMA", "HMK", "HMF")):
        return version >= 230.0
    if normalized.startswith("HMJ"):
        return version >= 116.0
    if normalized in {"HME-2", "HME-4", "TPM-CN"}:
        return version >= 122.0
    if normalized in {"HME-3", "HME-5"}:
        return version >= 120.0
    if normalized.startswith("HMG"):
        return version >= 154.0
    if normalized.startswith("HMI"):
        return version >= 126.0
    if normalized.startswith("VNS"):
        return version >= 139.0
    return False


def calculate_remote_id_cq(salt: str, mac: str, vid: str) -> str:
    if len(mac) < 4:
        return ""

    var1 = f"{vid}_{mac[:-4]}"
    var2 = f"{mac[1:len(mac)-2]}_{vid}"
    h1 = _text_for_rand(salt, var1)
    h2 = _stream_cipher_hex(f"{vid}{mac}", var2)
    return _code_util_encode(f"{h1}{h2}")[:24]


def _stream_cipher_hex(data: str, key: str) -> str:
    if not data or not key:
        return ""

    key_stream = _generate_key_stream(key, len(data))
    data_bytes = data.encode("utf-8")
    out = bytearray()
    for index, byte in enumerate(data_bytes):
        out.append(byte ^ key_stream[index % len(key_stream)])
    return out.hex()


def _generate_key_stream(key: str, length: int) -> list[int]:
    key_bytes = key.encode("utf-8")
    seed = 0
    for byte in key_bytes:
        seed = (seed * 31 + byte) % 2147483647

    key_stream: list[int] = []
    state = seed
    for _ in range(length):
        state = (state * 1664525 + 1013904223) % 4294967296
        key_stream.append((state ^ (state >> 16)) & 0xFF)
    return key_stream


def _code_util_encode(content: str) -> str:
    hash_bytes = hashlib.sha256(content.encode("utf-8")).digest()
    words = [int.from_bytes(hash_bytes[index * 4 : (index + 1) * 4], "big") for index in range(8)]
    final = bytearray(24)
    for index in range(24):
        word = words[index % 8]
        shift = (index // 8) * 8
        final[index] = (word >> shift) & 0xFF
    return _bytes_to_custom_encoding(final)


def _bytes_to_custom_encoding(data: bytes) -> str:
    charset = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    out: list[str] = []
    for byte in data:
        out.append(charset[byte % 62])
        out.append(charset[(byte * 31) % 62])
    return "".join(out)


def _text_for_rand(content: str, mac: str) -> str:
    if not content or not mac:
        return ""

    hex_content = content.encode("utf-8").hex()
    if len(hex_content) < 2:
        return ""

    parsed = int(hex_content[-2:], 16)
    rounds = parsed % 5 or 1

    processed = bytes.fromhex(hex_content)
    mac_bytes = mac.encode("utf-8")
    for _ in range(rounds):
        processed = _scramble(processed, mac_bytes)
    return processed.hex()


def _scramble(data: bytes, key: bytes) -> bytes:
    if not data:
        return b""
    perm = _build_permutation(key, len(data))
    return bytes(data[index] for index in perm)


def _build_permutation(key: bytes, size: int) -> list[int]:
    perm = list(range(size))
    if size <= 1:
        return perm

    key_len = len(key)
    if key_len == 0:
        return perm

    offset = 0
    for index in range(size):
        offset = (offset + perm[index] + key[index % key_len]) % size
        perm[index], perm[offset] = perm[offset], perm[index]
    return perm
