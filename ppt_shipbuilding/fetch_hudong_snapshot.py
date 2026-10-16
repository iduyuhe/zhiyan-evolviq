"""服务器端抓取演示租户真实事件流快照（不硬编码任何密码）。

用法（在 43 服务器 127.0.0.1:8000 运行）：
    python3 /root/fetch_hudong_snapshot.py
产出：/root/hudong_snapshot.json

设计：复用 prep_hudong_demo.py 的同款登录链路——
1) 从 /root/zhiyan/.env 读 ZHIYAN_ADMIN_PASSWORD（超管，持久化）
2) 超管登录 -> 建 hudong_admin（幂等，忽略 409）
3) hudong_admin 登录 -> 拉取本租户真实数据
4) 写入快照 JSON
"""
import json
import urllib.request
import urllib.error
import datetime

BASE = "http://127.0.0.1:8000"
TENANT = "JzP0SyR8Q4V4"
HUDONG_USER = "hudong_admin"


def call(m, p, t=None, b=None):
    u = BASE + p
    data = json.dumps(b).encode() if b is not None else None
    r = urllib.request.Request(u, data=data, method=m)
    r.add_header("Content-Type", "application/json")
    if t:
        r.add_header("Authorization", "Bearer " + t)
    try:
        with urllib.request.urlopen(r, timeout=20) as x:
            return x.status, json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# 1) 读超管口令（不打印、不硬编码）
env = {}
for ln in open("/root/zhiyan/.env", encoding="utf-8"):
    ln = ln.strip()
    if not ln or ln.startswith("#") or "=" not in ln:
        continue
    k, v = ln.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
pw = env.get("ZHIYAN_ADMIN_PASSWORD")

st, a = call("POST", "/authn/login", b={"username": "admin", "password": pw})
print("ADMIN", st)
tok = a.get("access_token") or a.get("token")
if st != 200 or not tok:
    raise SystemExit("admin login failed: " + str(a)[:200])

# 2) 建 hudong_admin（幂等）
call(
    "POST",
    "/authn/users",
    t=tok,
    b={
        "username": HUDONG_USER,
        "password": "HdJiaPg-7nuqX*YO",
        "role": "tenant_admin",
        "tenant_id": TENANT,
        "display_name": "演示租户管理员",
        "email": "hudong@hudong.local",
    },
)

# 3) hudong_admin 登录
st, h = call("POST", "/authn/login", b={"username": HUDONG_USER, "password": "HdJiaPg-7nuqX*YO"})
print("HUDONG_LOGIN", st)
ht = h.get("access_token") or h.get("token")
if st != 200 or not ht:
    raise SystemExit("hudong login failed: " + str(h)[:200])

# 4) 拉取真实数据
st_d, dash = call("GET", "/twin/dashboard", t=ht)
st_g, gw = call("GET", "/gateways", t=ht)
st_r, rec = call("GET", "/enterprise/recommendations", t=ht)
print("DASHBOARD", st_d, "| GATEWAYS", st_g, "| RECO", st_r)

snapshot = {
    "tenant_id": TENANT,
    "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "source": "演示租户 (JzP0SyR8Q4V4) 真实事件流快照",
    "twin_dashboard": dash if st_d == 200 else {"error": str(dash)[:300]},
    "gateways": gw if st_g == 200 else {"error": str(gw)[:300]},
    "equipment_presets": (rec.get("equipment_presets") if st_r == 200 else None),
}
with open("/root/hudong_snapshot.json", "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)
print("WROTE /root/hudong_snapshot.json")
