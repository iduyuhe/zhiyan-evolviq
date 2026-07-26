"""安装 git post-commit hook，使每次本地 commit 自动经服务器中转推送 GitHub。

从受版本控制的模板 scripts/hooks/post-commit.hook 复制为 .git/hooks/post-commit。
幂等：重复运行覆盖重写。复制时统一转 LF 换行，确保 Git Bash 的 sh 正确解析。

本安装器与模板均不含任何密钥；真正的中转推送脚本 scripts/_deploy/_push_sync.py
含服务器凭据，被 .gitignore 排除，仅存在于本地。
"""
import os
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], cwd=HERE
).decode("utf-8", "replace").strip()

TEMPLATE = os.path.join(HERE, "post-commit.hook")
HOOKS = os.path.join(ROOT, ".git", "hooks")
HOOK = os.path.join(HOOKS, "post-commit")

if not os.path.isfile(TEMPLATE):
    print("ERROR: template not found:", TEMPLATE)
    sys.exit(1)

os.makedirs(HOOKS, exist_ok=True)

# 以二进制读取并把所有换行统一为 LF，避免 Windows CRLF 让 sh 解析出错
with open(TEMPLATE, "rb") as f:
    data = f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
with open(HOOK, "wb") as f:
    f.write(data)

if os.name != "nt":
    st = os.stat(HOOK)
    os.chmod(HOOK, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

print("installed hook ->", HOOK)
