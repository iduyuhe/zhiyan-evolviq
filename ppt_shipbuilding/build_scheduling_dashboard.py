"""生成「造船生产排产决策看板」HTML——直接调用 aps_scheduler 造船感知模式，
把结构化输出渲染为自包含单文件 HTML（内联 CSS + SVG，无外部依赖），可离线打开。

数字一律来自后端 Agent 的确定性种子，零真名（船坞/船型/托盘均为匿名代号）。
"""
import asyncio
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.aps_scheduler.agent import aps_agent

OUT = os.path.join(os.path.dirname(__file__), "scheduling_dashboard.html")

NAVY = "#0B2545"
BLUE = "#2563EB"
CYAN = "#06B6D4"
AMBER = "#F59E0B"
RED = "#EF4444"
GREEN = "#10B981"
GREY = "#94A3B8"


def esc(s):
    return html.escape(str(s))


def bar(pct, color):
    return (f'<div class="bar"><div class="bar-fill" style="width:{pct}%;'
            f'background:{color}"></div><span class="bar-label">{pct}%</span></div>')


async def main():
    r = await aps_agent.analyze("对多船型并行造船的船坞窗口与托盘齐套做排产决策分析")
    k = r["kpis"]
    docks = r["docks"]
    hulls = r["hulls"]
    trays = r["trays"]
    wf = r["workforce"]
    ivs = r["interventions"]

    def risk_color(v, hi, mid):
        return RED if v >= hi else AMBER if v >= mid else GREEN

    # ---- KPI 卡 ----
    kpis = [
        ("平均船坞窗口就绪度", f"{k['avg_dock_readiness']}%", risk_color(k['avg_dock_readiness'], 70, 85), "安全线≥70%"),
        ("平均托盘齐套度", f"{k['avg_tray_readiness']}%", risk_color(100 - k['avg_tray_readiness'], 26, 20), "齐套线≥80%"),
        ("坞期风险船坞", f"{k['at_risk_dock_count']} 座", RED if k['at_risk_dock_count'] else GREEN, "共 3 座船坞"),
        ("节拍偏离船型", f"{k['behind_hull_count']} 艘", RED if k['behind_hull_count'] else GREEN, "共 6 艘船型"),
        ("待处理 ECN", f"{k['pending_ecn_count']} 条", AMBER if k['pending_ecn_count'] else GREEN, "设计变更高频"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-val" style="color:{c}">{v}</div>'
        f'<div class="kpi-name">{esc(n)}</div><div class="kpi-sub">{esc(s)}</div></div>'
        for n, v, c, s in kpis
    )

    # ---- 船坞甘特 ----
    maxp = 100
    gantt_rows = ""
    for d in docks:
        rc = risk_color(100 - d["window_readiness"], 30, 15)  # 低就绪度=红
        gantt_rows += (
            f'<div class="g-row"><div class="g-label">{esc(d["dock_id"])}<br><span class="g-sub">{esc(d["name"])}</span></div>'
            f'<div class="g-track">'
            f'<div class="g-seg cur" style="width:{d["current_progress"]}%" title="当前 {esc(d["current_hull"])}">{esc(d["current_hull"])} {d["current_progress"]}%</div>'
            f'<div class="g-seg nxt" style="width:{d["next_tray_readiness"]}%;background:{CYAN}" title="下一船型托盘齐套 {d["next_tray_readiness"]}%">下一 {esc(d["next_hull"])}</div>'
            f'<div class="g-flag" style="left:{d["window_readiness"]}%;background:{rc}"></div>'
            f'</div><div class="g-ready" style="color:{rc}">{d["window_readiness"]}%</div></div>'
        )

    # ---- 负荷热力 ----
    heat = ""
    for w in wf:
        c = risk_color(w["utilization"], 100, 90)
        heat += (f'<div class="heat-cell"><div class="heat-num" style="color:{c}">{w["utilization"]}%</div>'
                 f'<div class="heat-name">{esc(w["trade"])}</div>'
                 f'<div class="heat-sub">余量 {w["surplus_h"]}h</div></div>')

    # ---- 托盘齐套 ----
    tray_rows = ""
    for t in trays:
        c = risk_color(100 - t["readiness_pct"], 40, 20)
        tray_rows += (f'<div class="tray-row"><span class="tray-id">{esc(t["tray_id"])}</span>'
                      f'<span class="tray-scope">{esc(t["scope"])}</span>'
                      f'{bar(t["readiness_pct"], c)}'
                      f'<span class="tray-miss">缺 {t["missing"]}</span></div>')

    # ---- 干预卡 ----
    iv_cards = ""
    for iv in ivs:
        iv_cards += (
            f'<div class="iv"><div class="iv-head"><span class="iv-dot" style="background:{BLUE}"></span>'
            f'<b>{esc(iv["title"])}</b><span class="iv-conf">置信 {iv["confidence"]}</span></div>'
            f'<div class="iv-in"><span class="iv-k">输入</span>{esc(iv["input"])}</div>'
            f'<div class="iv-out"><span class="iv-k">输出</span>{esc(iv["output"])}</div>'
            f'<div class="iv-val">价值：{esc(iv["value"])}</div>'
            f'<div class="iv-status">人留终审 · {esc(iv["status"])}</div></div>'
        )

    # ---- What-if ----
    whatif = next((iv for iv in ivs if iv["id"] == "what_if"), None)
    wi_html = ""
    if whatif:
        wi_html = (f'<div class="wi"><div class="wi-title">What-if 排产推演</div>'
                   f'<div class="wi-body">{esc(whatif["output"])}</div>'
                   f'<div class="wi-mit">{esc(whatif["value"])}</div></div>')

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>造船生产排产决策看板 · 智衍 EvolvIQ</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:{NAVY};color:#E2E8F0;padding:28px}}
.wrap{{max-width:1180px;margin:0 auto}}
header{{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:18px;border-bottom:2px solid {BLUE};padding-bottom:14px}}
h1{{font-size:24px;color:#fff;letter-spacing:1px}}
.sub{{color:{CYAN};font-size:13px;margin-top:4px}}
.tag{{background:{BLUE};color:#fff;font-size:12px;padding:4px 10px;border-radius:14px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:22px}}
.kpi{{background:#10294d;border:1px solid #1e3a5f;border-radius:10px;padding:14px;text-align:center}}
.kpi-val{{font-size:26px;font-weight:700}}
.kpi-name{{font-size:13px;margin-top:6px;color:#CBD5E1}}
.kpi-sub{{font-size:11px;color:{GREY};margin-top:2px}}
.panel{{background:#10294d;border:1px solid #1e3a5f;border-radius:12px;padding:18px;margin-bottom:18px}}
.panel h2{{font-size:16px;color:#fff;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
.panel h2::before{{content:"";width:4px;height:16px;background:{CYAN};border-radius:2px;display:inline-block}}
.g-row{{display:flex;align-items:center;margin:10px 0}}
.g-label{{width:130px;font-size:13px}}
.g-sub{{font-size:11px;color:{GREY}}}
.g-track{{position:relative;flex:1;height:26px;background:#0a1c36;border-radius:6px;overflow:hidden;display:flex}}
.g-seg{{height:100%;display:flex;align-items:center;justify-content:center;font-size:11px;color:#fff;white-space:nowrap;padding:0 6px}}
.g-seg.cur{{background:{BLUE}}}
.g-seg.nxt{{opacity:.85}}
.g-flag{{position:absolute;top:-3px;width:3px;height:32px;transform:translateX(-50%)}}
.g-ready{{width:64px;text-align:right;font-size:13px;font-weight:600}}
.bar{{position:relative;flex:1;height:18px;background:#0a1c36;border-radius:5px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:5px}}
.bar-label{{position:absolute;right:6px;top:0;font-size:11px;line-height:18px;color:#fff}}
.heat{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.heat-cell{{background:#0a1c36;border-radius:8px;padding:14px;text-align:center}}
.heat-num{{font-size:22px;font-weight:700}}
.heat-name{{font-size:13px;margin-top:4px}}
.heat-sub{{font-size:11px;color:{GREY}}}
.tray-row{{display:flex;align-items:center;gap:12px;margin:8px 0;font-size:13px}}
.tray-id{{width:60px;color:{CYAN};font-weight:600}}
.tray-scope{{width:150px;color:#CBD5E1}}
.tray-miss{{width:60px;text-align:right;color:{AMBER};font-size:12px}}
.ivs{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
.iv{{background:#0a1c36;border-radius:10px;padding:14px;border-left:3px solid {BLUE}}}
.iv-head{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.iv-dot{{width:8px;height:8px;border-radius:50%}}
.iv-conf{{margin-left:auto;font-size:11px;color:{GREY}}}
.iv-in,.iv-out{{font-size:12px;margin:4px 0;line-height:1.5}}
.iv-k{{display:inline-block;width:34px;color:{CYAN};font-weight:600}}
.iv-val{{font-size:12px;color:#CBD5E1;margin-top:4px}}
.iv-status{{font-size:11px;color:{AMBER};margin-top:6px}}
.wi{{background:linear-gradient(135deg,#10294d,#0a1c36);border:1px solid {CYAN};border-radius:10px;padding:16px}}
.wi-title{{color:{CYAN};font-weight:700;margin-bottom:8px}}
.wi-body{{font-size:13px;line-height:1.6}}
.wi-mit{{font-size:12px;color:{GREEN};margin-top:8px}}
footer{{font-size:11px;color:{GREY};text-align:center;margin-top:10px;line-height:1.6}}
</style></head>
<body><div class="wrap">
<header><div><h1>造船生产排产决策看板</h1>
<div class="sub">智衍 EvolvIQ · 决策分身视角 · 懂造船约束的实时排产脑</div></div>
<div class="tag">G 模式 · 决策实时化率 MVP≥40%</div></header>

<div class="kpis">{kpi_html}</div>

<div class="panel"><h2>船坞窗口甘特（船坞=不可复制的瓶颈闸门）</h2>{gantt_rows}
<div style="font-size:11px;color:{GREY};margin-top:8px">蓝=当前船型进度 · 青=下一船型托盘齐套 · 竖标=窗口就绪度</div></div>

<div class="panel"><h2>关键工种负荷热力（多船型并行争用）</h2><div class="heat">{heat}</div></div>

<div class="panel"><h2>托盘齐套监控（后行窝工根因）</h2>{tray_rows}</div>

<div class="panel"><h2>五类排产决策干预（人留终审）</h2><div class="ivs">{iv_cards}</div></div>

<div class="panel"><h2>设计变更动态再平衡</h2>{wi_html}</div>

<footer>{esc(r.get('disclaimer',''))}<br>
本看板数字来自平台 APS Agent 造船感知模式的确定性演示种子，用于呈现决策逻辑；所有船坞/船型/托盘均为匿名代号，不指向任何真实船厂业绩。</footer>
</div></body></html>"""

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
    print("summary:", r["summary"])


if __name__ == "__main__":
    asyncio.run(main())
