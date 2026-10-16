import subprocess, sys, os

pptx = r"E:\agent_industry\zhiyan\ppt_shipbuilding\智衍造船行业版介绍.pptx"
cwd = os.path.dirname(pptx)
node = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
slidep = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-6\lib\node_modules\@tencent\slidep\dist\index.js"
pages = [f"{i:02d}" for i in range(1, 15)]

for idx, p in enumerate(pages):
    dsl = os.path.join(cwd, "slides", f"{p}.slide")
    r = subprocess.run([node, slidep, "upsert-dsl", pptx, "--dsl-file", dsl, "--page-index", str(idx)],
                       cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout
    ok = '"ok":true' in out and r.returncode == 0
    print(f"page {p} -> index {idx}: {'OK' if ok else 'FAIL'}")
    if not ok:
        print(out[:1200])
        if r.stderr.strip(): print("ERR:", r.stderr[:500])
        sys.exit(1)
print("BUILD DONE")
