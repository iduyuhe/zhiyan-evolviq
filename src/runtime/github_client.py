"""GitHub Issue 客户端——共生进化环「脱敏审核门 → 开源平台」落点

复用 scripts/_deploy/create_github_community.py 的 REST 模式，但改为运行时可调用的
纯函数，token 取自环境变量 GH_TOKEN（生产 .env 配置；脚本内联 token 不入库）。
韧性铁律：任何网络/鉴权失败均返回 None（绝不抛异常中断主流程），反馈仍落库。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

REPO = os.getenv("GH_REPO", "iduyuhe/zhiyan-evolviq")
API = "https://api.github.com"
_TOKEN = os.getenv("GH_TOKEN", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "zhiyan-symbiosis-bot",
    }


def create_issue(title: str, body: str, labels: list[str] | None = None) -> dict | None:
    """在 REPO 创建 Issue，返回 {'url','number'} 或 None（失败/未配置）。

    默认标签含 from-customer（共生进化环溯源标签）。
    """
    if not _TOKEN:
        logger.warning("⚠️ GH_TOKEN 未配置，跳过 Issue 创建（反馈仍落库，状态 pending_review）")
        return None
    labels = labels or ["from-customer"]
    payload = {"title": title, "body": body, "labels": labels}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API}/repos/{REPO}/issues", data=data, method="POST", headers=_headers()
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode())
            return {"url": j.get("html_url"), "number": j.get("number")}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300] if e.fp else ""
        logger.warning(f"⚠️ GitHub Issue 创建失败（HTTP {e.code}）：{detail}")
        return None
    except Exception as e:  # 网络/超时等
        logger.warning(f"⚠️ GitHub Issue 创建异常（反馈仍落库）：{e}")
        return None
