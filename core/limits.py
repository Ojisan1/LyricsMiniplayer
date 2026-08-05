"""Hard caps for untrusted remote content (LRCLIB / iTunes)."""

from __future__ import annotations

# JSON response bodies (LRCLIB get/search, iTunes search).
MAX_JSON_BYTES = 1_500_000  # 1.5 MB

# Lyric text after parsing.
MAX_LYRIC_LINES = 800
MAX_LYRIC_TEXT_BYTES = 100_000  # 100 KB

# Album art download / header inspection (before full pixel conversion).
MAX_IMAGE_BYTES = 8_000_000  # 8 MB
MAX_IMAGE_DIMENSION = 4096

# Combined in-memory lyrics + artwork cache.
MAX_CACHE_ENTRIES = 50
MAX_CACHE_BYTES = 50_000_000  # 50 MB

# Artwork HTTP redirects (each hop re-validated).
MAX_ARTWORK_REDIRECTS = 3
