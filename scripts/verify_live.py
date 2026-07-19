"""Live 验收探针：从服务器本机 curl runtime(8000) 验证全栈真实化。

验收目标：
- /health 可达（db 字段若存在则为 postgresql）
- /kg/stats mode == neo4j（非 memory 回退）
- /gateways 4 网关均 ready 且至少为部分 live（modbus/mqtt/opcua/ipc_cfx）
- DB 经 runtime 启动日志确认为 postgresql（外部不可达，故用日志佐证）
"""
import io
import logging
import socket

import paramiko

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("verify")

HOST = "43.153.172.52"
PORT = 22
USER = "root"
PASS = "Duyuhe2004"

PROBE = (
    "echo '=== /health ==='; curl -s --max-time 8 http://localhost:8000/health || echo HTTP_FAIL; "
    "echo; echo '=== /kg/stats ==='; curl -s --max-time 8 http://localhost:8000/kg/stats || echo HTTP_FAIL; "
    "echo; echo '=== /gateways ==='; curl -s --max-time 8 http://localhost:8000/gateways || echo HTTP_FAIL; "
    "echo; echo '=== runtime db mode (log) ==='; "
    "docker logs zhiyan-runtime-1 2>&1 | grep -iE '数据库就绪|回退本地|postgres|sqlite' | tail -5; "
    "echo '=== runtime kg mode (log) ==='; "
    "docker logs zhiyan-runtime-1 2>&1 | grep -iE 'neo4j|知识图谱|memory' | tail -5"
)


def run_robust(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    stdout.channel.settimeout(timeout)
    buf = io.StringIO()
    try:
        while True:
            data = stdout.read(4096)
            if not data:
                break
            buf.write(data.decode(errors="replace"))
    except socket.timeout:
        logger.warning("读取超时（命令可能仍在后台运行），仅返回已捕获部分")
    except Exception as e:  # noqa
        logger.warning("读取中断：%s", e)
    return buf.getvalue()


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
    logger.info("✅ SSH 已连接")
    out = run_robust(client, PROBE, timeout=30)
    print(out)
    client.close()


if __name__ == "__main__":
    main()
