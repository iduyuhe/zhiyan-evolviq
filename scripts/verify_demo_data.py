"""验证演示效果信号种子：注入后调参引擎应产出覆盖全部 3 类规则的建议。

直接调用 demo_seed.seed_demo_data()（不依赖 env），再跑 tuner.suggest() 断言。
运行：python scripts/verify_demo_data.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.core import demo_seed
from src.runtime.core.strategy_tuner import tuner


async def main() -> None:
    demo_seed.seed_demo_data()

    report = tuner.suggest()
    global_rpt = report["global"]
    suggestions = report["suggestions"]

    print("=== 全局效果报告 ===")
    print(f"  总会话        : {global_rpt['sessions']}")
    print(f"  总动作        : {global_rpt['total_actions']}")
    print(f"  自主动作      : {global_rpt['auto_actions']}")
    print(f"  自主率        : {global_rpt['autonomous_rate']:.1%}  (目标 {global_rpt['target_autonomous_rate']:.0%})")
    print(f"  节省工时(时)  : {global_rpt['time_saved_hours']}")
    print(f"  介入已决      : {global_rpt['interventions_decided']}")
    print(f"  介入准确率    : {global_rpt['intervention_accuracy']:.1%}")
    print(f"  达标          : {global_rpt['meets_target']}")

    print(f"\n=== 调参建议（共 {len(suggestions)} 条）===")
    for s in suggestions:
        print(f"  [{s['direction']:6}] {s['agent']:14} {s['param']:22} "
              f"{s['current']} -> {s['suggested']}  | {s['rationale'][:46]}")

    # ---- 断言：覆盖全部 3 类规则 ----
    params = {s["param"] for s in suggestions}
    dirs = {s["direction"] for s in suggestions}
    assert "confidence_threshold" in params, f"缺少 confidence_threshold 建议: {params}"
    assert "max_daily_autonomous" in params, f"缺少 max_daily_autonomous（提上限）建议: {params}"
    assert "tighten" in dirs, f"缺少收紧类建议: {dirs}"
    assert len(suggestions) >= 9, f"建议数偏少: {len(suggestions)}"

    print(f"\n✅ OK：演示数据产出 {len(suggestions)} 条建议，覆盖放宽(confidence_threshold) / "
          f"收紧(tighten) / 提上限(max_daily_autonomous) 全部 3 类规则。")


if __name__ == "__main__":
    asyncio.run(main())
