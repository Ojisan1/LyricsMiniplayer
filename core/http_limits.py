"""Helpers for reading remote responses under hard size caps."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from core.limits import MAX_JSON_BYTES

log = logging.getLogger(__name__)


def read_response_bytes(
    response: requests.Response,
    *,
    max_bytes: int,
    label: str,
) -> bytes | None:
    """Read a streamed response body up to *max_bytes*; None if oversized."""
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                log.warning("%s Content-Length %s exceeds %d bytes", label, content_length, max_bytes)
                return None
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64_000):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            log.warning("%s body exceeded %d bytes; discarding", label, max_bytes)
            return None
        chunks.append(chunk)
    return b"".join(chunks) if chunks else b""


def read_json_object(
    response: requests.Response,
    *,
    max_bytes: int = MAX_JSON_BYTES,
    label: str = "JSON response",
) -> Any | None:
    """Parse JSON from a streamed response, rejecting oversized bodies."""
    raw = read_response_bytes(response, max_bytes=max_bytes, label=label)
    if raw is None:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        log.warning("%s was not valid JSON", label)
        return None
