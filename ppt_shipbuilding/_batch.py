import subprocess, sys, os

pptx = r"E:\agent_industry\zhiyan\ppt_shipbuilding\智衍造船行业版介绍.pptx"
cwd = os.path.dirname(pptx)
slidep = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\slidep.cmd"
pages = ["02", "03", "04", "05", "06"]

for p in pages:
    dsl = os.path.join(cwd, "slides", f"{p}.slide")
    print(f"\n=== LINT {p} ===")
    r = subprocess.run([slidep, "lint", pptx, "--dsl-file", dsl], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout)
    if r.stderr.strip(): print("ERR:", r.stderr)
    if r.returncode != 0 or '"ok":true' not in r.stdout:
        print(f"LINT FAILED {p}")
        sys.exit(1)
    print(f"\n--- UPSERT {p} ---")
    r2 = subprocess.run([slidep, "upsert-dsl", pptx, "--dsl-file", dsl], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r2.stdout)
    if r2.stderr.strip(): print("ERR:", r2.stderr)
    if r2.returncode != 0 or '"ok":true' not in r2.stdout:
        print(f"UPSERT FAILED {p}")
        sys.exit(1)
print("\nALL OK 02-06")
