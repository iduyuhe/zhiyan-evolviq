import subprocess, json, os, sys

CRED = os.path.expanduser("~/.workbuddy/wechat_credentials.json")
cfg = json.load(open(CRED, encoding="utf-8"))
APPID = cfg["appid"]
SECRET = cfg["appsecret"]
BASE = "https://api.weixin.qq.com/cgi-bin"

def curl_json(url, method="GET", data_path=None, files=None):
    cmd = ["curl", "-sS", "--max-time", "90", "-X", method, url]
    if files:
        for field, path in files.items():
            cmd += ["-F", f"{field}=@{path}"]
    if data_path:
        cmd += ["-H", "Content-Type: application/json; charset=utf-8", "--data-binary", f"@{data_path}"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"curl failed: {p.stderr[:300]}")
    try:
        return json.loads(p.stdout)
    except Exception:
        raise RuntimeError(f"bad json: {p.stdout[:300]}")

# 1. token
r = curl_json(f"{BASE}/token?grant_type=client_credential&appid={APPID}&secret={SECRET}")
if "access_token" not in r:
    print("TOKEN FAIL", r); sys.exit(1)
TOKEN = r["access_token"]
print("TOKEN OK")

COVER = "E:/agent_industry/zhiyan/docs/wechat/cover_research_case_paradigm.jpg"
ECO = "C:/Users/Administrator/WorkBuddy/2026-05-29-19-34-45/.workbuddy/assets/ecosystem_banner.png"
RECRUIT = "C:/Users/Administrator/WorkBuddy/2026-05-29-19-34-45/.workbuddy/assets/recruit_banner.gif"

# 2. cover permanent -> thumb media_id + material url
r = curl_json(f"{BASE}/material/add_material?access_token={TOKEN}&type=image", method="POST", files={"media": COVER})
print("PERMANENT RAW:", r)
THUMB = r.get("media_id")
COVER_MAT_URL = r.get("url")
print("COVER PERMANENT media_id:", THUMB)
print("COVER PERMANENT url:", COVER_MAT_URL)

# 3. cover article-img -> body header url (uploadimg) - DIFFERENT URL from permanent
r = curl_json(f"{BASE}/media/uploadimg?access_token={TOKEN}", method="POST", files={"media": COVER})
HEAD_URL = r.get("url")
print("COVER ARTICLE-IMG url:", HEAD_URL)

# 4. ecosystem banner article-img
r = curl_json(f"{BASE}/media/uploadimg?access_token={TOKEN}", method="POST", files={"media": ECO})
ECO_URL = r.get("url")
print("ECO url:", ECO_URL)

# 5. recruit gif article-img
r = curl_json(f"{BASE}/media/uploadimg?access_token={TOKEN}", method="POST", files={"media": RECRUIT})
RECRUIT_URL = r.get("url")
print("RECRUIT url:", RECRUIT_URL)

# 6. build article HTML with replaced placeholders
html_path = "E:/agent_industry/zhiyan/docs/2026-07-29_deep_article.html"
html = open(html_path, encoding="utf-8").read()
html = html.replace("__HEAD_IMG__", HEAD_URL)
html = html.replace("__ECOSYSTEM_IMG__", ECO_URL)
html = html.replace("__RECRUIT_IMG__", RECRUIT_URL)
assert "__HEAD_IMG__" not in html and "__ECOSYSTEM_IMG__" not in html and "__RECRUIT_IMG__" not in html, "placeholder left!"
assert HEAD_URL.startswith("http"), f"head url bad: {HEAD_URL}"
assert "mmbiz.qpic.cn" in HEAD_URL, f"head url not mmbiz: {HEAD_URL}"

articles = [{
    "title": "破局工业智能体：当「研究案例范式」重构制造业数字化交付逻辑",
    "thumb_media_id": THUMB,
    "author": "杜玉河",
    "digest": "研究案例范式如何不等签约就建活体行业模型，让工业数字化的价值从项目费变成订阅费。",
    "show_cover_pic": 1,
    "content": html,
    "content_source_url": "",
    "need_open_comment": 0,
    "only_fans_can_comment": 0,
}]
data_path = "E:/agent_industry/zhiyan/docs/wechat/draft_research_case_paradigm.json"
with open(data_path, "w", encoding="utf-8") as f:
    json.dump({"articles": articles}, f, ensure_ascii=False)

# 7. create draft (DRAFT ONLY, no publish)
r = curl_json(f"{BASE}/draft/add?access_token={TOKEN}", method="POST", data_path=data_path)
print("DRAFT RAW:", r)
DRAFT_ID = r.get("media_id")
print("DRAFT media_id:", DRAFT_ID)
print("RESULT:", json.dumps({
    "thumb_media_id": THUMB,
    "head_url": HEAD_URL,
    "eco_url": ECO_URL,
    "recruit_url": RECRUIT_URL,
    "draft_media_id": DRAFT_ID,
}, ensure_ascii=False))
