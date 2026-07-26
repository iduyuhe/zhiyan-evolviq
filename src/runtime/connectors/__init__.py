"""社交通道接入包（v29.9）—— 把企业微信/钉钉/邮件的真实外部信号经 token 鉴权后
喂入 UNS `social` 通道，由 src.runtime.tacit_capture 订阅管道完成「抽取即锚定」。

这是战略「隐性捕获」从「演示态（仅 API 注入端点）」走向「生产态（真实平台拉取）」的关键一步：
- 企微：自建应用回调，SHA1 签名校验 + AES 消息体解密（cryptography 不可用时降级为 JSON 演示体）
- 钉钉：群机器人/连接平台回调，HmacSHA256 加签校验
- 邮件：IMAP 轮询，敏感内容走审批门（payload._needs_review=True）

韧性铁律：任一连接器不可用 / token 缺失 → 静默降级（enabled=False），绝不阻断启动与上游。
"""

from src.runtime.connectors.manager import SocialConnectorManager, manager

__all__ = ["SocialConnectorManager", "manager"]
