"""Tests for artwork URL allowlisting, size rewrite, and album ranking."""

from core.artwork import (
    _artwork_url,
    _is_allowed_url,
    _normalize,
    _pick_artwork_url,
    _score_result,
)


def test_artwork_url_rewrites_size_token():
    base = "https://is1-ssl.mzstatic.com/image/thumb/Music/x/y/z/100x100bb.jpg"
    assert _artwork_url(base, "1200x1200bb").endswith("1200x1200bb.jpg")
    assert _artwork_url(base, "600x600bb").endswith("600x600bb.jpg")


def test_is_allowed_url_artwork_hosts():
    assert _is_allowed_url(
        "https://is1-ssl.mzstatic.com/image/thumb/Music/x/100x100bb.jpg",
        for_artwork=True,
    )
    assert _is_allowed_url("https://mzstatic.com/art.jpg", for_artwork=True)
    assert not _is_allowed_url("http://is1-ssl.mzstatic.com/art.jpg", for_artwork=True)
    assert not _is_allowed_url(
        "https://evil.example/is1-ssl.mzstatic.com/art.jpg",
        for_artwork=True,
    )
    assert not _is_allowed_url(
        "https://user:pass@is1-ssl.mzstatic.com/art.jpg",
        for_artwork=True,
    )
    assert not _is_allowed_url(
        "https://is1-ssl.mzstatic.com:8443/art.jpg",
        for_artwork=True,
    )


def test_is_allowed_url_itunes_search_hosts():
    assert _is_allowed_url("https://itunes.apple.com/search", for_artwork=False)
    assert _is_allowed_url("https://www.itunes.apple.com/search", for_artwork=False)
    assert not _is_allowed_url("https://itunes.apple.com/search", for_artwork=True)
    assert not _is_allowed_url("https://evil.apple.com/search", for_artwork=False)


def test_normalize_folds_case_and_punctuation():
    assert _normalize("Café!") == "cafe"
    assert _normalize("Hello-World") == "hello world"


def test_score_result_prefers_album_match():
    title = _normalize("Song")
    artist = _normalize("Band")
    album = _normalize("The Album")
    exact_album = {
        "trackName": "Song",
        "artistName": "Band",
        "collectionName": "The Album",
    }
    wrong_album = {
        "trackName": "Song",
        "artistName": "Band",
        "collectionName": "Song - Single",
    }
    assert _score_result(
        exact_album, title_norm=title, artist_norm=artist, album_norm=album
    ) > _score_result(
        wrong_album, title_norm=title, artist_norm=artist, album_norm=album
    )


def test_pick_artwork_url_ranks_album_over_single():
    results = [
        {
            "trackName": "Forced Entry",
            "artistName": "Leprous",
            "collectionName": "Forced Entry - Single",
            "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/a/100x100bb.jpg",
        },
        {
            "trackName": "Forced Entry",
            "artistName": "Leprous",
            "collectionName": "Bilateral",
            "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/b/100x100bb.jpg",
        },
    ]
    picked = _pick_artwork_url(
        results,
        title="Forced Entry",
        artist="Leprous",
        album="Bilateral",
    )
    assert picked is not None
    assert "/Music/b/" in picked


def test_pick_artwork_url_rejects_disallowed_hosts():
    results = [
        {
            "trackName": "Song",
            "artistName": "Band",
            "collectionName": "Album",
            "artworkUrl100": "https://cdn.example.com/100x100bb.jpg",
        }
    ]
    assert (
        _pick_artwork_url(results, title="Song", artist="Band", album="Album") is None
    )
