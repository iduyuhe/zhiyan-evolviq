"""杜特第0号用户开通（S2.5 #313）——确定性租户 + 团队账号

走现有多租户 + JWT 体系，自建自用先行（上海杜特企业管理咨询有限公司）。
幂等：重复调用不重复建号；团队账号初始密码可经环境变量覆盖，否则用确定性回退。

调用点：main lifespan（启动期一次性）；测试可直接调用验证。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DUTE_TENANT_ID = "dute"
DUTE_TENANT_NAME = "上海杜特企业管理咨询有限公司"

# (username, role, display_name)
_DUTE_TEAM = [
    ("dute_admin", "tenant_admin", "杜特管理员"),
    ("duyuhe", "tenant_admin", "杜玉河"),
    ("dute_team", "operator", "杜特团队成员"),
]


async def seed_dute_tenant() -> dict:
    """开通杜特第0号租户 + 团队账号（幂等）。返回开通摘要。"""
    from src.runtime.authn.service import authn_service
    from src.runtime.tenant_store import tenant_store

    summary = {"tenant_id": DUTE_TENANT_ID, "created": False, "accounts": []}
    if tenant_store.get(DUTE_TENANT_ID) is None:
        try:
            _tid, _key = await tenant_store.register_with_id(DUTE_TENANT_ID, DUTE_TENANT_NAME)
            summary["created"] = True
            logger.info(f"🏢 杜特第0号租户已开通：tenant_id={_tid}")
        except Exception as e:
            logger.warning(f"⚠️ 杜特第0号租户开通失败（不阻断启动）：{e}")
            return summary
    else:
        logger.info("🏢 杜特第0号租户已存在（跳过重复开通）")

    for uname, role, disp in _DUTE_TEAM:
        pw = (
            os.environ.get(f"ZHIYAN_DUTE_PW_{uname.upper()}", "")
            or os.environ.get("ZHIYAN_DUTE_PW", "")
            or f"Dute@{uname}2026"
        )
        try:
            await authn_service.create_user(
                username=uname, password=pw, role=role,
                tenant_id=DUTE_TENANT_ID, display_name=disp,
            )
            summary["accounts"].append({"username": uname, "role": role, "password": pw})
            logger.info(f"👤 杜特团队账号已建：{uname}（{role}）初始密码: {pw}")
        except ValueError:
            # 已存在，跳过
            summary["accounts"].append({"username": uname, "role": role, "password": None})
    return summary
