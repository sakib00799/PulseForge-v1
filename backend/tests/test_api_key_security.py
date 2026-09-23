from app.core.security import create_api_key, hash_api_key


def test_production_api_key_is_hashed_and_prefixed() -> None:
    raw_key, prefix, key_hash = create_api_key(production=True)

    assert raw_key.startswith("pf_live_")
    assert prefix == raw_key[:16]
    assert key_hash == hash_api_key(raw_key)
    assert raw_key != key_hash


def test_non_production_api_key_uses_test_prefix() -> None:
    raw_key, _, _ = create_api_key(production=False)

    assert raw_key.startswith("pf_test_")
