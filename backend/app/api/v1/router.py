"""第一版接口路由汇总。"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.health import router as health_router
from app.api.v1.teacher_cases import router as teacher_cases_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(teacher_cases_router)
api_v1_router.include_router(admin_router)
