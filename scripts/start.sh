#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${1:-${PORT:-8793}}"
HOST="${HOST:-127.0.0.1}"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "错误：未检测到 Python 3。" >&2
  exit 1
fi

if ! "$PYTHON" -c "import pymysql, akshare" >/dev/null 2>&1; then
  echo "错误：缺少 Python 依赖，请先执行：" >&2
  echo "  $PYTHON -m pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f "dist/index.html" ]]; then
  echo "错误：未找到 React 构建产物，请先执行：" >&2
  echo "  npm install && npm run build" >&2
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "错误：未找到 .env，请根据 .env.example 配置数据库和大模型参数。" >&2
  exit 1
fi

echo "正在启动生财佑道后端：http://${HOST}:${PORT}/news"
echo "页面：/news · /analysis · /funds · /sitemap.xml"
echo "接口：/api/news · /api/wechat-articles · /api/etf-shares · /api/auth/* · /api/refresh-status"
exec env HOST="$HOST" PORT="$PORT" "$PYTHON" server.py
