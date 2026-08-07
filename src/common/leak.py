"""真实锚定名片段——零真名泄漏铁律单一真相源（2026-08-03 抽出）

设计动机：
- 原 `LEAK_TOKENS` 定义在 `compliance_reviewer/agent.py`，但该 agent 的 `analyze()`
  内部 `from src.agents.industry_research.agent import ...` 是重型 import；
  IM 桥接（im_bridge）若直接 import compliance_reviewer 会牵动整条 agent 链。
- 抽出为轻量单一真相源：compliance_reviewer / im_bridge / 各对外 agent 统一引用本文件，
  既保证令牌列表唯一一致，又避免 im_bridge 触碰重型依赖。

🔴 铁律：出站文本（IM 卡片 / 推文 / 对外视图）一律经 `sanitize_leak` 脱敏，绝不外发真名。
"""

# 🔴 真实锚定名片段（与测试 / 各 agent 匿名铁律完全一致）
# 2026-07-29 腿 B 首客 P3 扩展：第 2 案例（半导体·case_semicon_2026）真名片段一并封禁
LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte",
               "中芯", "688981", "00981", "SMIC", "smic",
               # 2026-08-03 第一批全球化锚：晶圆代工 + 光刻设备
               "台积电", "台積電", "TSMC", "tsmc", "2330",
               "阿斯麦", "阿斯麥", "ASML", "asml",
               # 2026-08-03 第二批（每行业 国际5+国内5）：半导体 7 家新锚
               # 全球 AI 算力芯片龙头
               "英伟达", "輝達", "NVIDIA", "nvidia", "NVDA", "黄仁勋", "黃仁勳", "Jensen Huang",
               # 全球存储与 IDM 巨头
               "三星电子", "三星電子", "三星", "Samsung", "samsung", "005930",
               # 全球封测龙头（⚠️ 绝无裸 "ASE"）
               "日月光投控", "日月光", "ASE Technology", "ASEH", "3711",
               # 国内半导体设备龙头
               "北方华创", "002371", "NAURA", "naura", "芯源微",
               # 国内图像传感器龙头（韦尔股份已更名豪威集团，新旧名皆封）
               "豪威集团", "韦尔股份", "豪威", "韦尔", "603501", "OmniVision", "omnivision",
               # 国内存储与 MCU 公司
               "兆易创新", "兆易", "603986", "GigaDevice", "gigadevice",
               # 国内封测龙头（长 token 在前：长电科技 > 长电微电子 > 长电微 > 长电）
               "长电科技", "长电微电子", "长电微", "长电", "600584", "JCET", "jcet", "晟碟"]


def contains_leak(text: str) -> list[str]:
    """返回文本中命中的真名片段列表（空列表=无泄漏）。"""
    if not text:
        return []
    return [t for t in LEAK_TOKENS if t and t in text]


def sanitize_leak(text: str, mask: str = "＊") -> str:
    """将文本中出现的真名片段统一替换为脱敏符（默认全角星）。

    长 token 在前替换，避免短 token 先命中导致长 token 残留（如「长电科技」先于「长电」）。
    """
    if not text:
        return text
    out = text
    # LEAK_TOKENS 已按「长在前」排序，但保险起见仍按长度降序再扫一遍
    for t in sorted(LEAK_TOKENS, key=len, reverse=True):
        if t:
            out = out.replace(t, mask)
    return out
