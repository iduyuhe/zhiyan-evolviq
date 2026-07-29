"""环境感知源适配器基类（v30.0 α，第⑥路 environment）

统一契约（与社交连接器 SocialConnectorBase 同构）：
- enabled：环境源默认启用（公开信息无需凭证）；mode 区分 live / simulated
- test_connection()：连通性探测，返回 {ok, latency_ms, detail, mode}
- fetch(limit)：抓取并归一为信号 dict 列表（live 失败自动回退 simulated —— 韧性铁律）
- pull(limit)：fetch + 逐条 publish 入 UNS environment 路（credibility 由源定级）

F4 可信治理：每个源适配器自带 credibility 定级（三类首批源均为 official——官方为锚）。
韧性铁律：任何网络/解析失败静默回退 simulated 样本，绝不阻断；网络 import 放函数内。
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class EnvSourceBase:
    """环境感知源基类。"""

    # 子类覆盖
    name: str = "base"
    kind: str = "environment"   # policy | market | benchmark
    label: str = "环境源"
    credibility: str = "official"  # F4：首批三类源均为官方（官方为锚）
    tenant_facing: bool = True   # 是否对租户开放订阅（False=平台级研究源，不占免费额度）

    def __init__(self) -> None:
        self.enabled: bool = True  # 公开信息源无需凭证，默认启用
        self._last_error: str | None = None
        self._last_pull_ts: float | None = None
        self._last_mode: str = "simulated"

    # ---- 子类实现：live 抓取 URL（settings 配置，空=simulated 演示态）----
    def _live_url(self) -> str:
        return ""

    # ---- 子类实现：simulated 演示样本（确定性，测试/演示一致）----
    def _simulated_samples(self, limit: int) -> list[dict]:
        raise NotImplementedError

    # ---- 子类可覆盖：解析 live 响应为信号列表 ----
    def _parse_live(self, text: str, limit: int) -> list[dict]:
        raise NotImplementedError

    # ---- 抓取（live 优先，失败回退 simulated）----
    async def fetch(self, limit: int = 10) -> tuple[list[dict], str]:
        url = self._live_url()
        if url:
            try:
                import httpx  # 延迟 import（韧性铁律）

                t0 = time.time()
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                signals = self._parse_live(resp.text, limit)
                if signals:
                    self._last_error = None
                    self._last_mode = "live"
                    logger.info(f"✅ [{self.name}] live 抓取 {len(signals)} 条（{time.time()-t0:.1f}s）")
                    return signals, "live"
            except Exception as e:
                self._last_error = str(e)
                logger.warning(f"⚠️ [{self.name}] live 抓取失败，回退 simulated（不破管）：{e}")
        self._last_mode = "simulated"
        return self._simulated_samples(limit), "simulated"

    # ---- 发布：信号入 UNS environment 路（credibility 由源定级）----
    def publish_signal(self, signal: dict) -> Any:
        try:
            from src.runtime.uns import uns

            payload = dict(signal)
            entities = payload.pop("entities", [])
            ev = uns.publish_environment(
                source=f"env://{self.kind}/{self.name}",
                payload=payload,
                entities=entities,
                type="env_signal",
                confidence=payload.pop("confidence", 1.0) if "confidence" in payload else 1.0,
                credibility=self.credibility,
            )
            return ev.id
        except Exception as e:
            logger.warning(f"⚠️ [{self.name}] 发布 UNS 失败（不破管）：{e}")
            return None

    async def pull(self, limit: int = 10) -> dict:
        signals, mode = await self.fetch(limit)
        published = 0
        for s in signals:
            if self.publish_signal(s) is not None:
                published += 1
        self._last_pull_ts = time.time()
        return {"source": self.name, "pulled": len(signals), "published": published, "mode": mode}

    # ---- 连通性测试 ----
    async def test_connection(self) -> dict:
        url = self._live_url()
        if not url:
            return {
                "name": self.name, "ok": True, "latency_ms": 0,
                "mode": "simulated", "detail": "未配置真实源 URL，演示态可用（配置后自动升级 live）",
            }
        try:
            import httpx

            t0 = time.time()
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
            ms = int((time.time() - t0) * 1000)
            ok = resp.status_code < 400
            return {"name": self.name, "ok": ok, "latency_ms": ms, "mode": "live",
                    "detail": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"name": self.name, "ok": False, "latency_ms": None, "mode": "live",
                    "detail": f"不可达（将自动回退 simulated）：{e}"}

    def status(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "label": self.label,
            "credibility": self.credibility,
            "tenant_facing": self.tenant_facing,
            "enabled": self.enabled,
            "mode": "live" if self._live_url() else "simulated",
            "last_mode": self._last_mode,
            "last_pull_ts": self._last_pull_ts,
            "error": self._last_error,
        }
