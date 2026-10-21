import pytest

from cairn.canonical import canonical_json, canonical_sha256


def test_canonical_json_sorts_keys_and_is_compact() -> None:
    assert canonical_json({"b": 1, "a": [1, 2], "c": "é"}) == ('{"a":[1,2],"b":1,"c":"é"}'.encode())


def test_canonical_hash_ignores_key_order() -> None:
    assert canonical_sha256({"x": 1, "y": 2}) == canonical_sha256({"y": 2, "x": 1})


def test_canonical_json_rejects_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
