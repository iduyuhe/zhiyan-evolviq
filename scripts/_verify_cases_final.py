"""最终校验：cases.json 合并 15 锚定后，配额/匿名性/零真名是否合规。"""
import json, sys
sys.path.insert(0, "src")
from collections import Counter
from common.leak import LEAK_TOKENS

CASE = "src/agents/case_curator/cases.json"
cases = json.load(open(CASE, encoding="utf-8"))
print(f"总锚定数: {len(cases)}")

REQ = ("case_id", "subject_anon", "industry", "industry_key", "real_anchor",
       "scope", "teaching_notes_anon", "teaching_notes_internal", "status", "updated_at")
errs = []
by_kv = {}
for a in cases:
    ik = a.get("industry_key")
    sc = a.get("scope")
    by_kv.setdefault(ik, Counter())[sc] += 1
    for k in REQ:
        if k not in a:
            errs.append(f"{a.get('case_id')} 缺字段 {k}")
    ra = a.get("real_anchor", "")
    ra_short = ra.split("（")[0].strip()
    for f in ("subject_anon", "teaching_notes_anon"):
        if ra_short and ra_short in (a.get(f) or ""):
            errs.append(f"{a['case_id']} 对外字段泄露真名: {f}")
    blob = (a.get("subject_anon", "") + a.get("teaching_notes_anon", ""))
    hit = [t for t in LEAK_TOKENS if t and t in blob]
    if hit:
        errs.append(f"{a['case_id']} 对外字段命中 LEAK_TOKENS: {hit}")

print("=== 最终配额分布（按 industry_key/scope）===")
for ik, c in by_kv.items():
    d, g = c.get("domestic", 0), c.get("global", 0)
    flag = "OK" if d <= 5 and g <= 5 else "❌超配额"
    print(f"  {ik}: domestic={d} global={g} 合计={d+g} {flag}")
    if d > 5 or g > 5:
        errs.append(f"{ik} 超配额")

print(f"\n错误数: {len(errs)}")
for e in errs:
    print("  -", e)
print("RESULT:", "PASS" if not errs else "FAIL")
sys.exit(1 if errs else 0)
