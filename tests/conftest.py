"""pytest 全局前置。

P1④ X-Tenant-Key 信任收紧后，非强制鉴权模式下的 X-Tenant-Key 默认必须是
已注册租户 key（fail-closed）。既有测试大量使用 "TENANT_A" 之类的裸租户名
作为隔离断言手段，因此测试环境显式声明开发信任开关，保持旧行为。

注意：必须在任何 src.* import 之前设置（authn.config 在 import 时读取 env）。
"""

import os

os.environ.setdefault("ZHIYAN_DEV_TRUST_TENANT_KEY", "1")

# P1③ 写回队列 SQLite 持久化：测试环境禁用落盘，
# 避免跨运行残留 pending 记录污染计数断言（test_writeback / test_tenant_isolation）。
os.environ.setdefault("ZHIYAN_WRITEBACK_DB", "disabled")
