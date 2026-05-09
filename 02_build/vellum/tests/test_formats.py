# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Tests for canonical JSON serialization."""

import json

from vellum.export.formats import canonical_json, canonical_json_str, content_hash


class TestCanonicalJson:
    def test_sorted_keys(self) -> None:
        data = {"z": 1, "a": 2, "m": 3}
        result = canonical_json_str(data)
        keys = list(json.loads(result).keys())
        assert keys == ["a", "m", "z"]

    def test_compact_separators(self) -> None:
        data = {"key": "value"}
        result = canonical_json_str(data)
        assert result == '{"key":"value"}'

    def test_nested_objects_sorted(self) -> None:
        data = {"outer": {"z": 1, "a": 2}}
        result = canonical_json_str(data)
        assert result == '{"outer":{"a":2,"z":1}}'

    def test_utf8_encoding(self) -> None:
        data = {"emoji": "\u2603"}
        result = canonical_json(data)
        assert isinstance(result, bytes)
        assert "\u2603".encode("utf-8") in result

    def test_deterministic_across_calls(self) -> None:
        data = {"b": [3, 1, 2], "a": {"y": 0, "x": 1}}
        r1 = canonical_json(data)
        r2 = canonical_json(data)
        assert r1 == r2

    def test_empty_dict(self) -> None:
        assert canonical_json_str({}) == "{}"

    def test_empty_list(self) -> None:
        assert canonical_json_str([]) == "[]"

    def test_none_value(self) -> None:
        assert canonical_json_str({"k": None}) == '{"k":null}'


class TestContentHash:
    def test_returns_hex_string(self) -> None:
        h = content_hash({"test": True})
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self) -> None:
        data = {"a": 1, "b": 2}
        assert content_hash(data) == content_hash(data)

    def test_different_data_different_hash(self) -> None:
        assert content_hash({"a": 1}) != content_hash({"a": 2})
