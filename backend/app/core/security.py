"""密码哈希与 JWT 访问令牌。

密码使用标准库 ``hashlib.pbkdf2_hmac`` 加盐哈希，避免额外引入 bcrypt
等需要本地编译的依赖。访问令牌只携带用户主键，角色与账号状态由每次
请求查库校验，确保冻结或调整角色后旧令牌立即失效。
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

_ALGORITHM = "HS256"
_HASH_NAME = "sha256"
_ITERATIONS = 120_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """生成带盐密码哈希，格式为 ``pbkdf2_sha256$轮数$盐$摘要``。"""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )
    return f"pbkdf2_{_HASH_NAME}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码与已存储哈希是否匹配。"""
    try:
        prefix, iterations_text, salt_hex, digest_hex = stored.split("$")
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, TypeError):
        return False

    if prefix != f"pbkdf2_{_HASH_NAME}":
        return False

    digest = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_access_token(user_id: int, expires_minutes: int, secret_key: str) -> str:
    """签发包含用户主键的短期访问令牌。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> int | None:
    """解析令牌并返回用户主键；无效或过期时返回 ``None``。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret_key,
            algorithms=[_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None

    subject = payload.get("sub")
    if subject is None:
        return None

    try:
        return int(subject)
    except (TypeError, ValueError):
        return None
