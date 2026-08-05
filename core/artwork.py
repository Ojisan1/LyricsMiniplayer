"""Album art fetch from the iTunes Search API (no API key)."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import requests

log = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
USER_AGENT = "SpotifyLyricsMiniplayer/0.1 (https://github.com/local/LyricsMiniplayer)"
REQUEST_TIMEOUT_S = 8
_ART_MAX_BYTES = 5_000_000
# iTunes artwork URLs end with a size token like 100x100bb.jpg.
_ARTWORK_SIZE = re.compile(r"\d+x\d+bb", re.IGNORECASE)
_PREFERRED_SIZES = ("1200x1200bb", "600x600bb")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _artwork_url(artwork_url_100: str, size_token: str) -> str:
    return _ARTWORK_SIZE.sub(size_token, artwork_url_100, count=1)


def _normalize(text: str) -> str:
    """Lowercase, strip diacritics/punctuation for loose title/album matching."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_ish = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return _NON_ALNUM.sub(" ", ascii_ish.casefold()).strip()


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
        score = _score_result(
            item,
            title_norm=title_norm,
            artist_norm=artist_norm,
            album_norm=album_norm,
        )
        if score < 0:
            continue
        ranked.append((score, -index, url.strip()))

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

    try:
        with requests.Session() as session:
            session.headers["User-Agent"] = USER_AGENT
            response = session.get(
                ITUNES_SEARCH_URL,
                params={
                    "term": term,
                    "media": "music",
                    "entity": "song",
                    "limit": 15,
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

    artwork_url_100 = _pick_artwork_url(
        results, title=title, artist=artist, album=album
    )
    # If album-qualified search over-filtered, retry without album in the term
    # but still score against the album when ranking.
    if artwork_url_100 is None and album:
        try:
            with requests.Session() as session:
                session.headers["User-Agent"] = USER_AGENT
                response = session.get(
                    ITUNES_SEARCH_URL,
                    params={
                        "term": " ".join(part for part in (title, artist) if part),
                        "media": "music",
                        "entity": "song",
                        "limit": 15,
                    },
                    timeout=REQUEST_TIMEOUT_S,
                )
                response.raise_for_status()
                payload = response.json()
            results = payload.get("results") if isinstance(payload, dict) else None
            if isinstance(results, list):
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
                    return data
    except Exception:
        log.exception("iTunes album art download failed")
        return None

    log.info("iTunes artwork download failed for %r", term)
    return None
