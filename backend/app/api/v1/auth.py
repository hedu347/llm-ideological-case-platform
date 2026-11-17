"""登录、退出、个人信息与密码修改接口。"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import Settings
from app.core.deps import CurrentUser, SessionDep
from app.core.response import fail, ok
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User

router = APIRouter(tags=["账号与权限"])


class LoginRequest(BaseModel):
    """登录请求。``role`` 可选，传了就与账号角色校验。"""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str | None = None


def user_payload(user: User) -> dict[str, object]:
    """返回前端消费的用户信息形状。"""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "avatar": user.avatar,
        "nickName": user.nick_name,
        "phone": user.phone,
        "intro": user.intro,
        "status": user.status,
        "createTime": user.create_time,
    }


@router.post("/auth/login", summary="登录")
async def login(
    request: Request,
    payload: LoginRequest,
    session: SessionDep,
) -> dict[str, object]:
    """校验账号密码并签发访问令牌。

    所有业务失败都返回 HTTP 200 + 非零 code，前端登录页依赖这一点展示
    提示；若返回 401，axios 拦截器会直接跳转登录页，反而看不到原因。
    """
    user = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        return fail(400, "账号、密码或角色不匹配")
    if payload.role and payload.role != user.role:
        return fail(400, "账号、密码或角色不匹配")
    if user.status == 1:
        return fail(400, "该账号已被冻结，请联系管理员")

    settings: Settings = request.app.state.settings
    token = create_access_token(
        user.id,
        settings.access_token_expire_minutes,
        settings.secret_key.get_secret_value(),
    )
    return ok(
        {
            "token": token,
            "expires_in": settings.access_token_expire_minutes * 60,
            "username": user.username,
            "role": user.role,
            "avatar": user.avatar,
            "user": {
                "id": user.id,
                "username": user.username,
                "nickName": user.nick_name,
                "role": user.role,
                "status": user.status,
            },
        }
    )


@router.post("/auth/logout", summary="退出登录")
async def logout(user: CurrentUser) -> dict[str, object]:
    """令牌无状态，退出由前端清除本地令牌完成。"""
    return ok(None, "已退出登录")


@router.get("/users/me", summary="获取本人信息")
async def get_me(user: CurrentUser) -> dict[str, object]:
    """返回当前登录用户的信息，不含密码。"""
    return ok(user_payload(user))


class UpdateProfileRequest(BaseModel):
    """本人可修改的基本信息。"""

    nickName: str | None = None
    phone: str | None = None
    intro: str | None = None
    avatar: str | None = None


@router.patch("/users/me", summary="修改本人信息")
async def update_me(
    payload: UpdateProfileRequest,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """局部更新昵称、电话、简介和头像。"""
    if payload.nickName is not None:
        user.nick_name = payload.nickName
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.intro is not None:
        user.intro = payload.intro
    if payload.avatar is not None:
        user.avatar = payload.avatar
    await session.commit()
    return ok(user_payload(user))


class ChangePasswordRequest(BaseModel):
    """修改密码请求，字段名沿用前端约定。"""

    oldPwd: str
    newPwd: str


@router.put("/users/me/password", summary="修改本人密码")
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """校验原密码后更新密码哈希。"""
    if not verify_password(payload.oldPwd, user.password_hash):
        return fail(400, "原密码不正确")
    if len(payload.newPwd) < 6:
        return fail(400, "新密码长度不能少于 6 位")
    user.password_hash = hash_password(payload.newPwd)
    await session.commit()
    return ok(None, "密码修改成功")
