"""Canonical JSON: the single serialisation used for every hash in Cairn."""

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> bytes:
    """Serialise with sorted keys, compact separators and UTF-8, rejecting NaN."""
    text = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_hex(canonical_json(value))
