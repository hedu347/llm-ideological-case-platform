"""统一业务响应结构。

成功与业务校验失败（HTTP 200）均使用本模块构造响应，前端按
``code`` 判断业务结果；HTTP 层面的 401/403/404/500 仍由全局异常
处理器返回，前端按状态码处理。
"""

from typing import Any


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    """构造成功或业务提示响应。"""
    return {"code": 0, "message": message, "data": data}
