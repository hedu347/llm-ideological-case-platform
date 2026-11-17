"""密码哈希与访问令牌的单元测试。"""

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    """同一密码应能通过哈希校验，错误密码应被拒绝。"""
    stored = hash_password("123456")
    assert stored != "123456"
    assert verify_password("123456", stored) is True
    assert verify_password("wrong", stored) is False


def test_token_roundtrip_returns_user_id() -> None:
    """令牌签发后应能解出用户主键。"""
    token = create_access_token(7, 60, "secret-1234567890")
    assert decode_access_token(token, "secret-1234567890") == 7


def test_token_with_wrong_secret_is_rejected() -> None:
    """使用不同密钥签发的令牌必须被拒绝。"""
    token = create_access_token(7, 60, "secret-1234567890")
    assert decode_access_token(token, "other-secret") is None


def test_expired_token_is_rejected(monkeypatch) -> None:
    """已过期令牌必须被拒绝。"""
    token = create_access_token(7, -1, "secret-1234567890")
    assert decode_access_token(token, "secret-1234567890") is None
