"""企业现状画像存储 + 凭证 Vault（两阶段实例化框架 · Phase 2 产品化）

契约来源：docs/ENTERPRISE_PROFILE_SCHEMA.md（2026-07-29 杜总 E2/D1/D2 定调）。

两大职责：
1. EnterpriseProfileStore —— 企业现状描述（声明式画像），租户隔离，JSON 落盘持久化。
2. CredentialVault —— 凭证加密存储（D2 铁律）：
   🔴 Fernet 对称加密落盘 + 租户隔离 + 绝不明文落库 / 绝不进日志 / 绝不进外发 payload。
   🔴 fail-closed：加密组件不可用时**拒绝存储**，绝不降级为明文。
   明文仅在 runtime 内存中经 reveal() 临时取出使用（仅供 connectors/writeback 实例化），
   任何 API 响应只回 vault_id 引用，永不回显明文。

韧性降级：落盘失败自动回退内存态（重启即失），读写不阻断。
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 存储路径（测试可用 env 覆盖到 tmp）
_DATA_DIR = os.environ.get(
    "ZHIYAN_ENTERPRISE_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"),
)

PROFILE_INDUSTRIES = ["半导体", "3C", "新能源汽车", "通讯", "光伏", "工程机械", "其他"]
CREDENTIAL_KINDS = [
    "erp_writeback",
    "gateway_opcua",
    "social_wecom",
    "social_dingtalk",
    "email_imap",
]
INTENT_CHOICES = ["暂不", "评估后", "现在就开"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnterpriseProfileStore:
    """企业现状画像注册表（租户隔离，JSON 落盘 + 内存态降级）。"""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join(_DATA_DIR, "enterprise_profiles.json")
        self._profiles: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self._profiles = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ 企业画像加载失败，降级内存态：{e}")
            self._profiles = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:  # 韧性降级：落盘失败不阻断
            logger.warning(f"⚠️ 企业画像落盘失败（内存态继续）：{e}")

    def upsert(self, tenant_id: str, profile: dict) -> dict:
        """写入/更新某租户的企业现状画像。credentials 明文字段一律剥离。"""
        clean = dict(profile)
        # 🔴 D2 铁律：画像存储绝不携带凭证明文——凭证只走 vault
        clean.pop("credentials", None)
        clean.pop("secret", None)
        clean.pop("password", None)
        clean["updated_at"] = _now_iso()
        self._profiles[tenant_id or "default"] = clean
        self._save()
        return clean

    def get(self, tenant_id: str) -> dict | None:
        return self._profiles.get(tenant_id or "default")


class CredentialVault:
    """凭证加密 Vault（D2 铁律：加密落盘 + 租户隔离 + fail-closed）。"""

    def __init__(self, path: str | None = None, key_path: str | None = None) -> None:
        self.path = path or os.path.join(_DATA_DIR, "credential_vault.json")
        self.key_path = key_path or os.path.join(_DATA_DIR, "vault.key")
        self._records: dict[str, dict] = {}  # vault_id -> {tenant_id, kind, cipher, created_at}
        self._fernet = self._init_fernet()
        self._load()

    def _init_fernet(self):
        """初始化 Fernet；key 持久化（不存在则生成）。加密不可用返回 None（fail-closed）。"""
        try:
            from cryptography.fernet import Fernet

            key = os.environ.get("ZHIYAN_VAULT_KEY", "")
            if not key:
                if os.path.exists(self.key_path):
                    with open(self.key_path, "rb") as f:
                        key = f.read().strip()
                else:
                    key = Fernet.generate_key()
                    os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
                    with open(self.key_path, "wb") as f:
                        f.write(key)
            if isinstance(key, str):
                key = key.encode()
            return Fernet(key)
        except Exception as e:
            logger.warning(f"⚠️ 凭证 vault 加密组件不可用（将 fail-closed 拒绝存储）：{e}")
            return None

    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ 凭证 vault 加载失败，降级内存态：{e}")
            self._records = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ 凭证 vault 落盘失败（内存态继续）：{e}")

    # ---------- 写入 ----------
    def store(self, tenant_id: str, kind: str, secret: dict | str) -> dict:
        """加密存入凭证，返回 vault 引用（不含明文）。

        🔴 fail-closed：加密不可用直接抛错，绝不明文落库。
        """
        if kind not in CREDENTIAL_KINDS:
            raise ValueError(f"kind 须为 {CREDENTIAL_KINDS} 之一")
        if self._fernet is None:
            raise RuntimeError("凭证 vault 加密组件不可用，拒绝存储（fail-closed，绝不明文落库）")
        plain = json.dumps(secret, ensure_ascii=False) if isinstance(secret, dict) else str(secret)
        cipher = self._fernet.encrypt(plain.encode()).decode()
        vault_id = str(uuid.uuid4())
        self._records[vault_id] = {
            "tenant_id": tenant_id or "default",
            "kind": kind,
            "cipher": cipher,
            "created_at": _now_iso(),
        }
        self._save()
        # 返回引用——绝不含明文/密文
        return {"vault_id": vault_id, "kind": kind, "tenant_id": tenant_id or "default"}

    # ---------- 读取 ----------
    def list_refs(self, tenant_id: str) -> list[dict]:
        """列出某租户的凭证引用（仅元数据，无明文/密文）。租户隔离。"""
        return [
            {"vault_id": vid, "kind": r["kind"], "created_at": r["created_at"]}
            for vid, r in self._records.items()
            if r.get("tenant_id") == (tenant_id or "default")
        ]

    def reveal(self, vault_id: str, tenant_id: str) -> str | None:
        """runtime 内部临时取明文（仅供 connectors/writeback 实例化调用）。

        🔴 跨租户取用一律返回 None（租户隔离）；绝不进日志。
        """
        rec = self._records.get(vault_id)
        if rec is None or rec.get("tenant_id") != (tenant_id or "default"):
            return None
        if self._fernet is None:
            return None
        try:
            return self._fernet.decrypt(rec["cipher"].encode()).decode()
        except Exception:
            return None

    def delete(self, vault_id: str, tenant_id: str) -> bool:
        """删除凭证（仅本租户）。"""
        rec = self._records.get(vault_id)
        if rec is None or rec.get("tenant_id") != (tenant_id or "default"):
            return False
        del self._records[vault_id]
        self._save()
        return True


# 进程级单例
profile_store = EnterpriseProfileStore()
credential_vault = CredentialVault()
