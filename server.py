#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""server.py —— 本地看板服务 + 六小时后台自动刷新(纯标准库)。
- 静态服务整个 investment-news 目录(看板、data、脚本)
- 服务启动后自动执行 scripts/fetch.py + scripts/digest.py,之后每 6 小时执行一次。
- POST /api/refresh 已禁用;GET /api/refresh-status 可查看后台任务状态。
跑法: python3 server.py [port]   默认 8793
"""
import os, sys, json, shutil, subprocess, threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8793"))
DEFAULT_DATA_FILE = os.path.join(HERE, "data.js")
DATA_FILE = os.path.abspath(os.environ.get("DATA_FILE", DEFAULT_DATA_FILE))
REFRESH_INTERVAL = 6 * 60 * 60
REFRESH_LOCK = threading.Lock()
REFRESH_STATE = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_ok": None,
    "error": "",
}


def child_env():
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    # 保证子进程能找到 claude(订阅模式)
    extra = "/opt/homebrew/bin:/usr/local/bin:" + os.path.expanduser("~/.local/bin")
    env["PATH"] = extra + ":" + env.get("PATH", "")
    env["DATA_FILE"] = DATA_FILE
    return env


def ensure_data_file():
    """命名卷首次挂载时，用镜像内置数据初始化运行时文件。"""
    if DATA_FILE == DEFAULT_DATA_FILE or os.path.exists(DATA_FILE):
        return
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    shutil.copyfile(DEFAULT_DATA_FILE, DATA_FILE)


def run_refresh():
    """执行一次抓取与摘要；同一时间只允许一个刷新任务运行。"""
    if not REFRESH_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "刷新任务已在运行"}
    REFRESH_STATE.update(running=True, last_started=datetime.now().isoformat(timespec="seconds"), error="")
    try:
        try:
            py = sys.executable
            env = child_env()
            r1 = subprocess.run([py, "scripts/fetch.py"], cwd=HERE, env=env,
                                capture_output=True, text=True, timeout=600)
            r2 = subprocess.run([py, "scripts/digest.py"], cwd=HERE, env=env,
                                capture_output=True, text=True, timeout=1200)
            ok = (r2.returncode == 0 and r1.returncode == 0)
            payload = {"ok": ok, "fetch": (r1.stdout or "")[-500:], "digest": (r2.stdout or "")[-500:]}
            if not ok:
                payload["error"] = ((r2.stderr or "") + (r1.stderr or ""))[-500:]
            if not ok:
                print("自动刷新失败:", payload.get("error", "未知错误"))
        except Exception as e:
            payload = {"ok": False, "error": str(e)}
            print("自动刷新异常:", e)
        REFRESH_STATE.update(
            running=False,
            last_finished=datetime.now().isoformat(timespec="seconds"),
            last_ok=bool(payload.get("ok")),
            error=payload.get("error", ""),
        )
        return payload
    finally:
        REFRESH_LOCK.release()


def refresh_loop():
    """启动时刷新一次，之后每 6 小时刷新。"""
    while True:
        print("开始后台自动刷新…")
        result = run_refresh()
        if result.get("ok"):
            print("后台自动刷新完成，下次刷新将在 6 小时后执行。")
        threading.Event().wait(REFRESH_INTERVAL)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass

    def _json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _data_js(self):
        try:
            with open(DATA_FILE, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            return self.send_error(404, "data.js 尚未生成")
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/api/refresh"):
            return self._json({"ok": False, "error": "已关闭手动刷新，系统每 6 小时自动更新"}, 405)
        self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/api/refresh-status"):
            return self._json(dict(REFRESH_STATE, interval_hours=6))
        if self.path.split("?", 1)[0] == "/data.js" and DATA_FILE != DEFAULT_DATA_FILE:
            return self._data_js()
        return super().do_GET()


if __name__ == "__main__":
    ensure_data_file()
    display_host = "localhost" if HOST in ("0.0.0.0", "127.0.0.1") else HOST
    print("看板服务已启动: http://%s:%d/index.html   (Ctrl+C 停止)" % (display_host, PORT))
    print("数据刷新策略:启动后自动刷新,之后每 6 小时刷新一次(不支持手动刷新)")
    threading.Thread(target=refresh_loop, name="auto-refresh", daemon=True).start()
    # 本机默认只绑定回环地址；容器通过 HOST=0.0.0.0 显式开放监听。
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
