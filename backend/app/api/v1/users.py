"""管理员用户管理与操作记录接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require_roles
from app.core.response import fail, ok
from app.core.security import hash_password
from app.core.timeutil import now_text, today_compact
from app.models import AuditLog, User

router = APIRouter(tags=["账号与权限"])
AdminUser = Annotated[User, Depends(require_roles("admin"))]

ROLE_NAMES = {"student": "学生", "teacher": "教师", "admin": "管理员"}


def user_record(user: User) -> dict[str, object]:
    """返回用户列表行，避免泄露密码哈希。"""
    return {
        "id": user.id,
        "username": user.username,
        "nickName": user.nick_name,
        "role": user.role,
        "status": user.status,
        "phone": user.phone,
        "createTime": user.create_time,
    }


def add_audit(
    session: AsyncSession,
    operator: User,
    action: str,
    target: str,
    detail: str,
) -> None:
    """登记管理员关键操作。"""
    session.add(
        AuditLog(
            operator=operator.nick_name or operator.username,
            username=operator.username,
            action=action,
            target=target,
            detail=detail,
            time=now_text(),
        )
    )


def _normalize_page(page: int, size: int) -> tuple[int, int]:
    return max(1, page), min(max(1, size), 100)


@router.get("/users", summary="管理员查询用户列表")
async def list_users(
    admin: AdminUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    role: str = "",
) -> dict[str, object]:
    """按关键词与角色筛选用户。"""
    page, size = _normalize_page(page, size)
    statement = select(User)
    if keyword:
        like = f"%{keyword}%"
        statement = statement.where(
            User.username.like(like) | User.nick_name.like(like)
        )
    if role:
        statement = statement.where(User.role == role)

    total = (
        await session.execute(select(func.count()).select_from(statement.subquery()))
    ).scalar_one()
    users = (
        await session.execute(
            statement.order_by(User.id).offset((page - 1) * size).limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [user_record(user) for user in users],
            "page": page,
            "size": size,
        }
    )


class CreateUserRequest(BaseModel):
    """管理员创建账号请求。"""

    username: str
    nickName: str | None = None
    role: str = "student"
    phone: str | None = None
    intro: str | None = None
    password: str | None = None


@router.post("/users", summary="管理员创建账号")
async def create_user(
    payload: CreateUserRequest,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """创建账号，未指定密码时使用初始密码 123456。"""
    if not payload.username.strip():
        return fail(400, "请填写登录名")
    exists = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if exists is not None:
        return fail(400, "登录名已存在")
    if payload.role not in ROLE_NAMES:
        return fail(400, "角色不合法")

    password = payload.password or "123456"
    user = User(
        username=payload.username,
        password_hash=hash_password(password),
        role=payload.role,
        nick_name=payload.nickName or payload.username,
        phone=payload.phone or "",
        intro=payload.intro or "",
        status=0,
        create_time=today_compact(),
    )
    session.add(user)
    await session.flush()
    add_audit(
        session,
        admin,
        "创建账号",
        user.username,
        f"角色：{ROLE_NAMES.get(user.role, user.role)}",
    )
    await session.commit()
    return ok(
        {"id": user.id, "username": user.username, "initialPwd": password},
        "账号已创建",
    )


class UpdateUserRequest(BaseModel):
    """调整角色或冻结账号。"""

    role: str | None = None
    status: int | None = None


@router.patch("/users/{user_id}", summary="调整角色或冻结账号")
async def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """调整角色或冻结/解冻账号，并记录操作。"""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if payload.role is not None and payload.role != user.role:
        if payload.role not in ROLE_NAMES:
            return fail(400, "角色不合法")
        previous = user.role
        user.role = payload.role
        add_audit(
            session,
            admin,
            "调整角色",
            user.username,
            f"角色：{ROLE_NAMES.get(previous, previous)} → "
            f"{ROLE_NAMES.get(payload.role, payload.role)}",
        )

    if payload.status is not None and payload.status != user.status:
        user.status = payload.status
        if user.status == 1:
            add_audit(session, admin, "冻结账号", user.username, "账号冻结，令牌失效")
        else:
            add_audit(session, admin, "解冻账号", user.username, "账号恢复")

    await session.commit()
    return ok(user_record(user), "更新成功")


@router.post("/users/{user_id}/reset-password", summary="重置账号密码")
async def reset_password(
    user_id: int,
    admin: AdminUser,
    session: SessionDep,
) -> dict[str, object]:
    """把指定账号密码重置为初始密码。"""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password("123456")
    add_audit(session, admin, "重置密码", user.username, "重置为初始密码")
    await session.commit()
    return ok({"userId": user.id, "initialPwd": "123456"}, "密码已重置为 123456")


@router.get("/audit-logs", summary="查询关键操作记录")
async def list_audit_logs(
    admin: AdminUser,
    session: SessionDep,
    page: int = 1,
    size: int = 10,
) -> dict[str, object]:
    """按时间倒序返回操作记录。"""
    page, size = _normalize_page(page, size)
    total = (
        await session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()
    logs = (
        await session.execute(
            select(AuditLog)
            .order_by(AuditLog.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return ok(
        {
            "total": total,
            "records": [
                {
                    "id": log.id,
                    "operator": log.operator,
                    "username": log.username,
                    "action": log.action,
                    "target": log.target,
                    "detail": log.detail,
                    "time": log.time,
                }
                for log in logs
            ],
            "page": page,
            "size": size,
        }
    )
