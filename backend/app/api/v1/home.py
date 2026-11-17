"""首页平台数据接口。"""

from fastapi import APIRouter

from app.core.deps import SessionDep
from app.core.response import ok
from app.services.stats import build_home_index

router = APIRouter(tags=["首页"])


@router.get("/home/index-data", summary="首页平台数据")
async def home_index_data(session: SessionDep) -> dict[str, object]:
    """公开返回平台规模数据，供首页指标卡展示。"""
    return ok(await build_home_index(session))
