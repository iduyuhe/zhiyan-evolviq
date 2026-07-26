"""演示用 ERP/MES 审计接收端（v29.2）——让回写实执行路径在零外部依赖下闭环。

启用：env ZHIYAN_DS_DEMO_AUDIT=1 时，main lifespan 启动线程内 HTTP 服务，
监听 ZHIYAN_DS_DEMO_AUDIT_PORT（默认 8800），接收 POST /audit/records。
同时把 MES/ERP 连接器的 base_url 指向该服务，使 writeback_bridge.submit 走真实
HTTP POST → 200 路径（不再是 pending stub）。

这证明「智衍决策 → 业务系统审计记录」的闭环可在任意环境端到端跑通；
生产环境只需把 ZHIYAN_DS_MES_URL / ZHIYAN_DS_ERP_URL 指向真实 ERP/MES 即可同样生效。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logger = logging.getLogger(__name__)

_received: list[dict] = []
_lock = threading.Lock()
_server: "ThreadingHTTPServer | None" = None
_port: int = 8800


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip("/") not in ("/audit/records", "/audit/records/"):
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw or b"{}")
        except Exception as e:
            self._send(400, {"error": str(e)})
            return
        with _lock:
            rec = {"received_at": time.time(), **data}
            _received.append(rec)
        self._send(200, {"ok": True, "received_at": rec["received_at"]})

    def do_GET(self):
        if self.path.rstrip("/") not in ("/audit/records", "/audit/records/"):
            self._send(404, {"error": "not found"})
            return
        with _lock:
            self._send(200, {"records": list(_received), "count": len(_received)})

    def log_message(self, *args):  # 静默 HTTP 访问日志
        pass


def received() -> list[dict]:
    with _lock:
        return list(_received)


def start(port: int = 8800) -> int:
    """启动演示接收端（幂等）。返回实际监听端口。"""
    global _server, _port
    if _server is not None:
        return _port
    _port = port
    _server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    logger.info(f"🧪 演示审计接收端已启动 http://127.0.0.1:{port}/audit/records")
    return _port


def stop() -> None:
    global _server
    if _server is not None:
        _server.shutdown()
        _server = None
