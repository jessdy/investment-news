#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""server.py —— 本地看板服务 + 六小时后台自动刷新。
- 静态服务整个 investment-news 目录，并通过 API 从 MySQL 提供看板数据
- 服务启动后自动执行 scripts/fetch.py + scripts/digest.py,之后每 6 小时执行一次。
- POST /api/refresh 已禁用;GET /api/refresh-status 可查看后台任务状态。
跑法: python3 server.py [port]   默认 8793
"""
import os, sys, json, shutil, subprocess, threading, re
from datetime import datetime
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from database import read_news_data, read_wechat_content

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8793"))
STATIC_DIR = os.path.abspath(os.environ.get("STATIC_DIR", os.path.join(HERE, "dist")))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
DEFAULT_DATA_FILE = os.path.join(HERE, "data.js")
DATA_FILE = os.path.abspath(os.environ.get("DATA_FILE", DEFAULT_DATA_FILE))
AUTO_REFRESH = os.environ.get("AUTO_REFRESH", "true").lower() not in ("0", "false", "no")
REFRESH_INTERVAL = 6 * 60 * 60
REFRESH_LOCK = threading.Lock()
REFRESH_STATE = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_ok": None,
    "error": "",
}

SEO_PAGES = {
    "/news": {
        "title": "产业资讯｜全球产业链最新动态与 AI 关键信号 - 生财佑道",
        "description": "聚合全球权威信源，追踪人工智能、机器人、半导体等重点产业链动态，并提炼每日关键产业信号。",
        "heading": "全球产业资讯与关键产业信号",
        "keywords": "产业资讯,产业链,人工智能,机器人,半导体,科技新闻,行业动态",
    },
    "/analysis": {
        "title": "产业分析｜AI、机器人与科技趋势深度研究 - 生财佑道",
        "description": "生财佑道原创产业分析，深度解读人工智能、机器人、科技创新与商业趋势，提供长期产业研究视角。",
        "heading": "产业分析与科技趋势深度研究",
        "keywords": "产业分析,行业研究,人工智能,机器人,科技趋势,商业分析,生财佑道",
    },
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
            r3 = None
            if r1.returncode == 0 and r2.returncode == 0:
                r3 = subprocess.run([py, "scripts/import_mysql.py"], cwd=HERE, env=env,
                                    capture_output=True, text=True, timeout=180)
            ok = bool(r3 is not None and r3.returncode == 0)
            payload = {
                "ok": ok,
                "fetch": (r1.stdout or "")[-500:],
                "digest": (r2.stdout or "")[-500:],
                "database": (r3.stdout or "")[-500:] if r3 else "摘要不完整，已保留数据库上一版数据",
            }
            if not ok:
                errors = (r1.stderr or "") + (r2.stderr or "")
                if r3:
                    errors += r3.stderr or ""
                payload["error"] = errors[-500:] or payload["database"]
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
        super().__init__(*a, directory=STATIC_DIR, **k)

    def log_message(self, *a):
        pass

    def _json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
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

    def _public_base_url(self):
        if PUBLIC_BASE_URL:
            return PUBLIC_BASE_URL
        host = self.headers.get("Host", "localhost:%d" % PORT)
        if not re.fullmatch(r"[A-Za-z0-9.:[\]-]+", host):
            host = "localhost:%d" % PORT
        proto = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0].strip()
        if proto not in ("http", "https"):
            proto = "http"
        return "%s://%s" % (proto, host)

    def _route_content(self, path):
        entries = []
        last_modified = ""
        if path == "/news":
            data = read_news_data()
            last_modified = data.get("generated_at", "")
            for industry in data.get("industries", []):
                for item in industry.get("items", [])[:3]:
                    entries.append({
                        "name": item.get("zh") or item.get("title") or "产业资讯",
                        "url": item.get("url") or "",
                        "description": item.get("summary") or "",
                    })
        else:
            data = read_wechat_content()
            last_modified = data.get("importedAt", "")
            for article in data.get("articles", [])[:20]:
                entries.append({
                    "name": article.get("title") or "产业分析",
                    "url": article.get("url") or "",
                    "description": article.get("summary") or "",
                })
        return entries[:30], last_modified

    def _spa_html(self, path):
        index_file = os.path.join(STATIC_DIR, "index.html")
        try:
            with open(index_file, "r", encoding="utf-8") as file:
                page = file.read()
        except FileNotFoundError:
            return self.send_error(503, "前端构建产物不存在")

        seo = SEO_PAGES[path]
        base_url = self._public_base_url()
        canonical_url = base_url + path
        try:
            entries, last_modified = self._route_content(path)
        except Exception as error:
            print("生成 SEO 首屏内容失败:", error)
            entries, last_modified = [], ""

        item_list = [{
            "@type": "ListItem",
            "position": position,
            "name": entry["name"],
            "url": entry["url"],
        } for position, entry in enumerate(entries, 1) if entry["url"]]
        graph = [
            {
                "@type": "WebSite",
                "@id": base_url + "/#website",
                "url": base_url + "/",
                "name": "生财佑道产业资讯",
                "inLanguage": "zh-CN",
            },
            {
                "@type": "CollectionPage",
                "@id": canonical_url + "#webpage",
                "url": canonical_url,
                "name": seo["title"],
                "description": seo["description"],
                "isPartOf": {"@id": base_url + "/#website"},
                "inLanguage": "zh-CN",
            },
        ]
        if item_list:
            graph.append({
                "@type": "ItemList",
                "name": seo["heading"],
                "itemListElement": item_list,
            })
        structured_data = json.dumps(
            {"@context": "https://schema.org", "@graph": graph},
            ensure_ascii=False,
        ).replace("</", "<\\/")

        head = """
    <meta name="description" content="{description}" />
    <meta name="keywords" content="{keywords}" />
    <meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1" />
    <link rel="canonical" href="{canonical}" />
    <meta property="og:type" content="website" />
    <meta property="og:locale" content="zh_CN" />
    <meta property="og:site_name" content="生财佑道产业资讯" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:url" content="{canonical}" />
    <meta name="twitter:card" content="summary_large_image" />
    <script type="application/ld+json" data-seo-route>{structured_data}</script>
""".format(
            title=escape(seo["title"], quote=True),
            description=escape(seo["description"], quote=True),
            keywords=escape(seo["keywords"], quote=True),
            canonical=escape(canonical_url, quote=True),
            structured_data=structured_data,
        )

        links = "".join(
            '<li><a href="{url}">{name}</a><p>{description}</p></li>'.format(
                url=escape(entry["url"], quote=True),
                name=escape(entry["name"]),
                description=escape(entry["description"]),
            )
            for entry in entries if entry["url"]
        )
        fallback = (
            '<main aria-label="SEO 首屏内容"><h1>%s</h1><p>%s</p>'
            '<ul>%s</ul></main>'
        ) % (escape(seo["heading"]), escape(seo["description"]), links)

        page = re.sub(r"<title>.*?</title>", "<title>%s</title>" % escape(seo["title"]), page, flags=re.S)
        page = re.sub(r'\s*<meta\s+name="description"[\s\S]*?/>\s*', "\n", page, count=1)
        page = page.replace("</head>", head + "  </head>")
        page = page.replace('<div id="root"></div>', '<div id="root">%s</div>' % fallback)
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=300")
        if last_modified:
            self.send_header("X-Content-Updated-At", str(last_modified))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, code=308):
        self.send_response(code)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _sitemap(self):
        base_url = escape(self._public_base_url(), quote=True)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>%s/news</loc><changefreq>daily</changefreq><priority>1.0</priority></url>'
            '<url><loc>%s/analysis</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>'
            '</urlset>'
        ) % (base_url, base_url)
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _robots(self):
        body = "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % self._public_base_url()
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.path.startswith("/api/refresh"):
            return self._json({"ok": False, "error": "已关闭手动刷新，系统每 6 小时自动更新"}, 405)
        self.send_error(404)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._redirect("/news")
        if path in ("/news/", "/analysis/"):
            return self._redirect(path.rstrip("/"))
        if path in SEO_PAGES:
            return self._spa_html(path)
        if path == "/sitemap.xml":
            return self._sitemap()
        if path == "/robots.txt":
            return self._robots()
        if path == "/api/news":
            try:
                return self._json(read_news_data())
            except Exception as error:
                print("读取 MySQL 资讯数据失败:", error)
                return self._json({"ok": False, "error": "产业数据暂时不可用"}, 503)
        if path == "/api/wechat-articles":
            try:
                return self._json(read_wechat_content())
            except Exception as error:
                print("读取 MySQL 公众号数据失败:", error)
                return self._json({"ok": False, "error": "公众号数据暂时不可用"}, 503)
        if path == "/api/refresh-status":
            return self._json(dict(REFRESH_STATE, interval_hours=6))
        if path == "/data.js" and DATA_FILE != DEFAULT_DATA_FILE:
            return self._data_js()
        return super().do_GET()


if __name__ == "__main__":
    ensure_data_file()
    if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        raise SystemExit("未找到前端构建产物，请先运行 npm install && npm run build")
    display_host = "localhost" if HOST in ("0.0.0.0", "127.0.0.1") else HOST
    print("看板服务已启动: http://%s:%d/news   (Ctrl+C 停止)" % (display_host, PORT))
    if AUTO_REFRESH:
        print("数据刷新策略:启动后自动刷新,之后每 6 小时刷新一次(不支持手动刷新)")
        threading.Thread(target=refresh_loop, name="auto-refresh", daemon=True).start()
    else:
        print("数据自动刷新已关闭")
    # 本机默认只绑定回环地址；容器通过 HOST=0.0.0.0 显式开放监听。
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
