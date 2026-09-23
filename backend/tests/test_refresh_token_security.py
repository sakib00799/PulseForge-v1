from app.core.security import create_refresh_token, hash_refresh_token


def test_refresh_token_is_stored_as_hash() -> None:
    raw_token, token_hash, expires_at = create_refresh_token()

    assert raw_token != token_hash
    assert hash_refresh_token(raw_token) == token_hash
    assert len(token_hash) == 64
    assert expires_at.tzinfo is not None


def test_refresh_tokens_are_unique() -> None:
    first, _, _ = create_refresh_token()
    second, _, _ = create_refresh_token()

    assert first != second
