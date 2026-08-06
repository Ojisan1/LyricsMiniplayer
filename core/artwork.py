"""Album art fetch from the iTunes Search API (no API key)."""

from __future__ import annotations

import logging
import re
import unicodedata
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image

from core.cache import media_cache
from core.http_limits import read_json_object, read_response_bytes
from core.limits import (
    MAX_ARTWORK_REDIRECTS,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_DIMENSION,
    MAX_JSON_BYTES,
)

log = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
USER_AGENT = "SpotifyLyricsMiniplayer/1.2.1 (https://github.com/Ojisan1/LyricsMiniplayer)"
REQUEST_TIMEOUT_S = 8
# iTunes artwork URLs end with a size token like 100x100bb.jpg.
_ARTWORK_SIZE = re.compile(r"\d+x\d+bb", re.IGNORECASE)
_PREFERRED_SIZES = ("1200x1200bb", "600x600bb")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
}
_ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}


def _art_cache_key(title: str, artist: str, album: str) -> tuple[str, str, str, str]:
    return (
        "art",
        title.strip().lower(),
        artist.strip().lower(),
        album.strip().lower(),
    )


def _artwork_url(artwork_url_100: str, size_token: str) -> str:
    return _ARTWORK_SIZE.sub(size_token, artwork_url_100, count=1)


def _normalize(text: str) -> str:
    """Lowercase, strip diacritics/punctuation for loose title/album matching."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_ish = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return _NON_ALNUM.sub(" ", ascii_ish.casefold()).strip()


def _host_allowed(hostname: str | None, *, for_artwork: bool) -> bool:
    host = (hostname or "").lower().rstrip(".")
    if not host:
        return False
    if for_artwork:
        return host == "mzstatic.com" or host.endswith(".mzstatic.com")
    return host in {"itunes.apple.com", "www.itunes.apple.com"}


def _is_allowed_url(url: str, *, for_artwork: bool) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    return _host_allowed(parsed.hostname, for_artwork=for_artwork)


def _content_type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in _ALLOWED_IMAGE_TYPES


def _validate_image_bytes(data: bytes) -> bytes | None:
    """Accept JPEG/PNG under dimension caps using header inspection only."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in _ALLOWED_IMAGE_FORMATS:
                log.warning("Album art format %r rejected", image.format)
                return None
            width, height = image.size
            if (
                width < 1
                or height < 1
                or width > MAX_IMAGE_DIMENSION
                or height > MAX_IMAGE_DIMENSION
            ):
                log.warning(
                    "Album art dimensions %dx%d exceed %d; discarding",
                    width,
                    height,
                    MAX_IMAGE_DIMENSION,
                )
                return None
        return data
    except Exception:
        log.debug("Album art failed image header validation", exc_info=True)
        return None


def _download_image(url: str, session: requests.Session) -> bytes | None:
    """Download image bytes with URL, redirect, type, size, and dimension checks."""
    current = url
    try:
        for _ in range(MAX_ARTWORK_REDIRECTS + 1):
            if not _is_allowed_url(current, for_artwork=True):
                log.warning("Album art URL rejected: %s", current)
                return None

            response = session.get(
                current,
                timeout=REQUEST_TIMEOUT_S,
                stream=True,
                allow_redirects=False,
            )
            try:
                if response.is_redirect or response.status_code in {
                    301,
                    302,
                    303,
                    307,
                    308,
                }:
                    location = response.headers.get("Location")
                    if not location:
                        return None
                    current = urljoin(current, location)
                    continue

                response.raise_for_status()
                if not _content_type_allowed(response.headers.get("Content-Type")):
                    log.warning(
                        "Album art Content-Type rejected: %s",
                        response.headers.get("Content-Type"),
                    )
                    return None

                raw = read_response_bytes(
                    response,
                    max_bytes=MAX_IMAGE_BYTES,
                    label="Album art",
                )
            finally:
                response.close()

            if raw is None:
                return None
            return _validate_image_bytes(raw)

        log.warning("Album art exceeded %d redirects", MAX_ARTWORK_REDIRECTS)
        return None
    except requests.RequestException:
        log.debug("Album art download failed for %s", url, exc_info=True)
        return None


def _score_result(
    item: dict[str, Any],
    *,
    title_norm: str,
    artist_norm: str,
    album_norm: str,
) -> int:
    """Higher is better. Album match outranks a bare popularity hit."""
    track_norm = _normalize(str(item.get("trackName") or ""))
    collection_norm = _normalize(str(item.get("collectionName") or ""))
    artist_hit = _normalize(str(item.get("artistName") or ""))
    if not track_norm:
        return -1

    score = 0
    if title_norm and track_norm == title_norm:
        score += 100
    elif title_norm and (
        track_norm.startswith(title_norm + " ") or title_norm in track_norm
    ):
        # Remix / edit / featuring variants of the same title.
        score += 40
    else:
        return -1

    if album_norm:
        if collection_norm == album_norm:
            score += 80
        elif album_norm in collection_norm or collection_norm in album_norm:
            score += 50
        else:
            score -= 30

    if artist_norm and artist_norm in artist_hit:
        score += 20
    elif artist_norm and artist_hit and artist_hit not in artist_norm:
        score -= 10

    # Mild preference for the primary song entry over a long remix title.
    if title_norm and track_norm == title_norm:
        score += 5
    return score


def _pick_artwork_url(
    results: list[Any],
    *,
    title: str,
    artist: str,
    album: str,
) -> str | None:
    title_norm = _normalize(title)
    artist_norm = _normalize(artist)
    album_norm = _normalize(album)
    ranked: list[tuple[int, int, str]] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            continue
        url = item.get("artworkUrl100")
        if not isinstance(url, str) or not url.strip() or not _ARTWORK_SIZE.search(url):
            continue
        candidate = url.strip()
        if not _is_allowed_url(candidate, for_artwork=True):
            continue
        score = _score_result(
            item,
            title_norm=title_norm,
            artist_norm=artist_norm,
            album_norm=album_norm,
        )
        if score < 0:
            continue
        ranked.append((score, -index, candidate))

    if not ranked:
        return None
    ranked.sort(reverse=True)
    best_score, _, best_url = ranked[0]
    log.info(
        "iTunes art match score=%d (album=%r title=%r)",
        best_score,
        album or "",
        title,
    )
    return best_url


def _itunes_search(
    session: requests.Session,
    term: str,
) -> list[Any] | None:
    if not _is_allowed_url(ITUNES_SEARCH_URL, for_artwork=False):
        return None
    response = session.get(
        ITUNES_SEARCH_URL,
        params={
            "term": term,
            "media": "music",
            "entity": "song",
            "limit": 15,
        },
        timeout=REQUEST_TIMEOUT_S,
        stream=True,
        allow_redirects=False,
    )
    try:
        if response.is_redirect:
            log.warning("iTunes search redirected unexpectedly")
            return None
        response.raise_for_status()
        payload = read_json_object(
            response,
            max_bytes=MAX_JSON_BYTES,
            label="iTunes search",
        )
    finally:
        response.close()

    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    return results


def fetch_album_art(title: str, artist: str, album: str = "") -> bytes | None:
    """Return raw JPEG/PNG bytes for the best matching iTunes artwork, or None.

    When *album* is provided, prefer an iTunes hit whose collection matches it so
    compilation / single artwork does not win over the album Spotify is playing.
    """
    title = title.strip()
    artist = artist.strip()
    album = album.strip()
    term = " ".join(part for part in (title, artist, album) if part)
    if not title and not artist:
        return None

    cache_key = _art_cache_key(title, artist, album)
    cached = media_cache.get(cache_key)
    if isinstance(cached, (bytes, bytearray)):
        log.debug("Album art cache hit for %r", term)
        return bytes(cached)

    try:
        with requests.Session() as session:
            session.headers["User-Agent"] = USER_AGENT
            results = _itunes_search(session, term)
    except (requests.RequestException, ValueError):
        log.exception("iTunes album art search failed")
        return None

    artwork_url_100 = None
    if results is not None:
        artwork_url_100 = _pick_artwork_url(
            results, title=title, artist=artist, album=album
        )

    # If album-qualified search over-filtered, retry without album in the term
    # but still score against the album when ranking.
    if artwork_url_100 is None and album:
        try:
            with requests.Session() as session:
                session.headers["User-Agent"] = USER_AGENT
                results = _itunes_search(
                    session,
                    " ".join(part for part in (title, artist) if part),
                )
            if results is not None:
                artwork_url_100 = _pick_artwork_url(
                    results, title=title, artist=artist, album=album
                )
        except (requests.RequestException, ValueError):
            log.exception("iTunes album art fallback search failed")

    if artwork_url_100 is None:
        log.info("No iTunes artwork for %r", term)
        return None

    try:
        with requests.Session() as session:
            session.headers["User-Agent"] = USER_AGENT
            for size_token in _PREFERRED_SIZES:
                url = _artwork_url(artwork_url_100, size_token)
                data = _download_image(url, session)
                if data:
                    log.info(
                        "Album art fetched (%d bytes, %s)",
                        len(data),
                        size_token,
                    )
                    media_cache.put(cache_key, data, len(data))
                    return data
    except Exception:
        log.exception("iTunes album art download failed")
        return None

    log.info("iTunes artwork download failed for %r", term)
    return None
