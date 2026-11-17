"""认证与权限依赖。

令牌只携带用户主键；每次请求都重新查库获取角色与账号状态，因此管理员
冻结账号或调整角色后，既有令牌立即按新状态生效。
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models import User

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def get_optional_user(
    request: Request,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """解析令牌并返回用户；无令牌或令牌无效时返回 ``None``。

    返回的冻结用户由 ``get_current_user`` 判定为 403，以区分"未登录"
    与"账号被冻结"两种错误。
    """
    token = _extract_token(authorization)
    if token is None:
        return None

    settings: Settings = request.app.state.settings
    user_id = decode_access_token(token, settings.secret_key.get_secret_value())
    if user_id is None:
        return None

    return await session.get(User, user_id)


async def get_current_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    """要求已登录且账号未冻结。"""
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    if user.status == 1:
        raise HTTPException(status_code=403, detail="账号已被冻结")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """构造角色校验依赖。"""

    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="无操作权限")
        return user

    return dependency
