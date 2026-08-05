"""公开演示账号播种（2026-08-05）

对外公布的 Demo 用专属账号：角色 viewer（看得到全部智能体、不能改配置/管用户），
密码公开、可经 ZHIYAN_DEMO_PW 覆盖。幂等：重复调用不重复建号。

解决的问题：只给网址、别人卡在登录页进不去——本账号 + 登录页提示，让任何人打开
网址即可登入体验演示数据（演示数据为全局注入，不按租户隔离；default 租户免用量计量）。

🔴 安全边界：绝不使用 admin / 研究案例租户作为公开凭证；本账号权限严格低于 tenant_admin，
无法管理用户、租户、系统配置，仅能浏览与发起 Agent 会话（sessions 接口不卡角色）。
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEMO_USER = "demo"
DEMO_DISPLAY = "公开演示账号"
DEMO_TENANT = "default"  # default 租户免用量计量；演示数据为全局注入，不依赖租户


def default_password() -> str:
    """公开演示密码（可经环境变量覆盖）。

    ⚠️ 前端登录页提示文案中写死的也是本默认值；
       若经 ZHIYAN_DEMO_PW 改了后端密码，须同步更新 Login.tsx 的提示文案。
    """
    return os.environ.get("ZHIYAN_DEMO_PW", "") or "EvolvIQ2026"


async def seed_demo_account() -> dict:
    """开通公开演示账号（幂等）。"""
    from src.runtime.authn.service import authn_service

    pw = default_password()
    try:
        await authn_service.create_user(
            username=DEMO_USER,
            password=pw,
            role="viewer",
            tenant_id=DEMO_TENANT,
            display_name=DEMO_DISPLAY,
        )
        logger.info("👤 公开演示账号已建：%s（viewer，密码经 ZHIYAN_DEMO_PW 可覆盖）", DEMO_USER)
        return {"created": True, "username": DEMO_USER}
    except ValueError:
        # 已存在：幂等跳过（如需改密码，经 ZHIYAN_DEMO_PW 后手动 sync 或重建容器）
        logger.info("👤 公开演示账号已存在（跳过）：%s", DEMO_USER)
        return {"created": False, "username": DEMO_USER}
