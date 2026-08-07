"""一次性校验：_new_anchors.json 能否安全并入案例库。"""
import json
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = os.path.join(BASE, "src/agents/case_curator/_new_anchors.json")
CASE = os.path.join(BASE, "src/agents/case_curator/cases.json")

REQ = ["case_id", "subject_anon", "industry", "industry_key", "real_anchor",
       "scope", "recommended_interfaces", "teaching_notes_anon",
       "teaching_notes_internal", "status", "updated_at", "disclosure_facts"]

new = json.load(open(NEW, encoding="utf-8"))
cases = json.load(open(CASE, encoding="utf-8"))

errs = []
existing_ids = {c["case_id"] for c in cases}
new_ids = set()

# 1) schema + scope + 配额
from collections import Counter
by_kv = {}
for a in new:
    cid = a.get("case_id")
    if cid in new_ids:
        errs.append(f"DUP case_id within new: {cid}")
    new_ids.add(cid)
    if cid in existing_ids:
        errs.append(f"DUP case_id vs cases.json: {cid}")
    for k in REQ:
        if k not in a:
            errs.append(f"{cid} 缺字段 {k}")
    scope = a.get("scope")
    if scope not in ("domestic", "global"):
        errs.append(f"{cid} scope 非法: {scope}")
    ik = a.get("industry_key")
    if ik not in ("telecom", "consumer_electronics", "new_energy"):
        errs.append(f"{cid} industry_key 非法: {ik}")
    df = a.get("disclosure_facts") or {}
    if "source" not in df or "fiscal_year" not in df or "facts" not in df:
        errs.append(f"{cid} disclosure_facts 不完整")
    # 匿名性：对外字段不得含真实锚定名
    ra = a.get("real_anchor", "")
    for field in ("subject_anon", "teaching_notes_anon"):
        if ra and ra.split("（")[0] in (a.get(field) or ""):
            errs.append(f"{cid} 对外字段泄露真名: {field}")
    # 配额
    by_kv.setdefault(ik, Counter())[scope] += 1

print("=== 配额分布（新增，按 industry_key/scope）===")
for ik, c in by_kv.items():
    d, g = c.get("domestic", 0), c.get("global", 0)
    flag = "OK" if d <= 5 and g <= 5 else "❌超配额"
    print(f"  {ik}: domestic={d} global={g} 合计={d+g} {flag}")
    if d > 5 or g > 5:
        errs.append(f"{ik} 超配额")

# 2) 合并后总配额（含既有 cases.json）
merged = cases + new
by_kv2 = {}
for a in merged:
    by_kv2.setdefault(a["industry_key"], Counter())[a["scope"]] += 1
print("=== 合并后总配额（含既有）===")
for ik, c in by_kv2.items():
    d, g = c.get("domestic", 0), c.get("global", 0)
    flag = "OK" if d <= 5 and g <= 5 else "❌超配额"
    print(f"  {ik}: domestic={d} global={g} 合计={d+g} {flag}")

# 3) LEAK_TOKENS 不得出现在对外字段
from src.common.leak import LEAK_TOKENS
for a in new:
    blob = (a.get("subject_anon", "") + a.get("teaching_notes_anon", ""))
    hit = [t for t in LEAK_TOKENS if t in blob]
    if hit:
        errs.append(f"{a['case_id']} 对外字段命中 LEAK_TOKENS: {hit}")

print(f"\n新增锚定数: {len(new)}")
print(f"既有锚定数: {len(cases)}")
print(f"错误数: {len(errs)}")
for e in errs:
    print("  -", e)
sys.exit(1 if errs else 0)
