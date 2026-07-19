#!/usr/bin/env python3
"""把修复后的 infra/docker-compose.yml 传到服务器并跑 `docker compose config` 校验。

仅校验语法与变量展开，不构建、不改任何运行中的容器。
凭证走环境变量，不落盘。
"""
import os
import paramiko
import sys

HOST = os.environ["SSH_HOST"]
PORT = int(os.environ.get("SSH_PORT", 22))
USER = os.environ["SSH_USER"]
PASS = os.environ["SSH_PASS"]

LOCAL = os.path.join(os.path.dirname(__file__), "..", "infra", "docker-compose.yml")
REMOTE_FILE = "/root/zhiyan/infra/docker-compose.yml"


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

    # 1) 上传修复版
    sftp = cli.open_sftp()
    lpath = os.path.abspath(LOCAL)
    sftp.put(lpath, REMOTE_FILE)
    sftp.close()
    print(f"[OK] 已上传 {lpath} -> {REMOTE_FILE}")

    # 2) 跑 config 校验（不构建）
    cmd = (
        "cd /root/zhiyan && "
        "docker compose -f infra/docker-compose.yml config >/tmp/cfg.out 2>/tmp/cfg.err; "
        "echo EXIT:$?; echo '--- stderr ---'; cat /tmp/cfg.err"
    )
    stdin, stdout, stderr = cli.exec_command(cmd)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(out)
    if err.strip():
        print("[stderr]", err)

    # 3) 提取关键服务构建上下文确认
    grep = cli.exec_command(
        "cd /root/zhiyan && grep -nE 'context:|dockerfile:' infra/docker-compose.yml"
    )[1].read().decode(errors="replace")
    print("--- 修复后构建上下文 ---")
    print(grep)

    cli.close()


if __name__ == "__main__":
    main()
