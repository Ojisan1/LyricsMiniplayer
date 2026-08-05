"""Album art fetch from the iTunes Search API (no API key)."""

from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
USER_AGENT = "SpotifyLyricsMiniplayer/0.1 (https://github.com/local/LyricsMiniplayer)"
REQUEST_TIMEOUT_S = 8
_ART_MAX_BYTES = 5_000_000
# iTunes artwork URLs end with a size token like 100x100bb.jpg.
_ARTWORK_SIZE = re.compile(r"\d+x\d+bb", re.IGNORECASE)
_PREFERRED_SIZES = ("1200x1200bb", "600x600bb")


def _artwork_url(artwork_url_100: str, size_token: str) -> str:
    return _ARTWORK_SIZE.sub(size_token, artwork_url_100, count=1)


def _download_image(url: str, session: requests.Session) -> bytes | None:
    """Download image bytes with a hard size cap. Returns None on any failure."""
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_S, stream=True)
        response.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64_000):
            if not chunk:
                continue
            total += len(chunk)
            if total > _ART_MAX_BYTES:
                log.warning("Album art exceeded %d bytes; discarding", _ART_MAX_BYTES)
                return None
            chunks.append(chunk)
        if not chunks:
            return None
        return b"".join(chunks)
    except requests.RequestException:
        log.debug("Album art download failed for %s", url, exc_info=True)
        return None


def fetch_album_art(title: str, artist: str) -> bytes | None:
    """Return raw JPEG/PNG bytes for the best matching iTunes artwork, or None."""
    term = " ".join(part for part in (title.strip(), artist.strip()) if part)
    if not term:
        return None

    try:
        with requests.Session() as session:
            session.headers["User-Agent"] = USER_AGENT
            response = session.get(
                ITUNES_SEARCH_URL,
                params={
                    "term": term,
                    "media": "music",
                    "entity": "song",
                    "limit": 5,
                },
                timeout=REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
            payload = response.json()
    except (requests.RequestException, ValueError):
        log.exception("iTunes album art search failed")
        return None

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return None

    artwork_urls: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("artworkUrl100")
        if isinstance(url, str) and url.strip() and _ARTWORK_SIZE.search(url):
            artwork_urls.append(url.strip())

    if not artwork_urls:
        log.info("No iTunes artwork for %r", term)
        return None

    # Prefer the first hit's higher resolutions; fall through other results only
    # if every preferred size fails to download.
    try:
        with requests.Session() as session:
            session.headers["User-Agent"] = USER_AGENT
            for artwork_url_100 in artwork_urls:
                for size_token in _PREFERRED_SIZES:
                    url = _artwork_url(artwork_url_100, size_token)
                    data = _download_image(url, session)
                    if data:
                        log.info(
                            "Album art fetched (%d bytes, %s)",
                            len(data),
                            size_token,
                        )
                        return data
    except Exception:
        log.exception("iTunes album art download failed")
        return None

    log.info("iTunes artwork download failed for %r", term)
    return None
