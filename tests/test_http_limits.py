"""Tests for HTTP size-cap helpers with mocked responses."""

from unittest.mock import MagicMock

from core.http_limits import read_json_object, read_response_bytes


def _stream_response(chunks: list[bytes], headers: dict[str, str] | None = None):
    response = MagicMock()
    response.headers = headers or {}
    response.iter_content = MagicMock(return_value=iter(chunks))
    return response


def test_read_response_bytes_joins_chunks():
    response = _stream_response([b"hel", b"lo"])
    assert read_response_bytes(response, max_bytes=10, label="test") == b"hello"


def test_read_response_bytes_rejects_content_length():
    response = _stream_response([b"data"], headers={"Content-Length": "100"})
    assert read_response_bytes(response, max_bytes=50, label="test") is None
    response.iter_content.assert_not_called()


def test_read_response_bytes_rejects_oversized_stream():
    response = _stream_response([b"12345", b"67890"])
    assert read_response_bytes(response, max_bytes=8, label="test") is None


def test_read_response_bytes_empty_body():
    response = _stream_response([])
    assert read_response_bytes(response, max_bytes=10, label="test") == b""


def test_read_json_object_parses_object():
    response = _stream_response([b'{"ok": true, "n": 1}'])
    assert read_json_object(response, max_bytes=100, label="json") == {
        "ok": True,
        "n": 1,
    }


def test_read_json_object_rejects_invalid_json():
    response = _stream_response([b"{nope"])
    assert read_json_object(response, max_bytes=100, label="json") is None


def test_read_json_object_rejects_oversized():
    response = _stream_response([b'{"a":"'], headers={"Content-Length": "9999"})
    assert read_json_object(response, max_bytes=10, label="json") is None
