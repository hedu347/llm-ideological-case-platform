"""时间格式化工具。

前端约定日期为 ``YYYYMMDD``、时间为 ``YYYY-MM-DD HH:mm``，本模块集中
生成这两种格式，避免各路由重复拼接。
"""

from datetime import datetime


def now_text() -> str:
    """返回 ``YYYY-MM-DD HH:mm`` 格式的当前时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_compact() -> str:
    """返回 ``YYYYMMDD`` 格式的当天日期。"""
    return datetime.now().strftime("%Y%m%d")
