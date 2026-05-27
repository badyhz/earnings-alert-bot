import pytest
from feishu_client import sign_feishu_webhook


def test_signing_produces_base64():
    secret = "test_secret"
    timestamp = "1234567890"
    result = sign_feishu_webhook(secret, timestamp)
    # Should be base64 encoded
    assert isinstance(result, str)
    assert len(result) > 0
    # Base64 decode should work
    import base64
    try:
        base64.b64decode(result)
    except Exception:
        pytest.fail("Result is not valid base64")


def test_signing_deterministic():
    secret = "my_secret"
    timestamp = "9999999999"
    sig1 = sign_feishu_webhook(secret, timestamp)
    sig2 = sign_feishu_webhook(secret, timestamp)
    assert sig1 == sig2


def test_signing_different_secrets():
    timestamp = "1234567890"
    sig1 = sign_feishu_webhook("secret1", timestamp)
    sig2 = sign_feishu_webhook("secret2", timestamp)
    assert sig1 != sig2


def test_signing_different_timestamps():
    secret = "same_secret"
    sig1 = sign_feishu_webhook(secret, "1111111111")
    sig2 = sign_feishu_webhook(secret, "2222222222")
    assert sig1 != sig2
