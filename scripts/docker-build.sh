#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="${IMAGE_NAME:-investment-news}"
IMAGE_TAG="${1:-${IMAGE_TAG:-latest}}"

for required_file in package.json package-lock.json vite.config.ts requirements.txt; do
  if [[ ! -f "$required_file" ]]; then
    echo "错误：缺少构建文件 $required_file" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "错误：未检测到 Docker，请先安装并启动 Docker Desktop。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "错误：Docker 服务未运行，请先启动 Docker Desktop。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "错误：未检测到 Docker Compose 插件。" >&2
  exit 1
fi

echo "正在构建 React 前端与 Python 后端镜像 ${IMAGE_NAME}:${IMAGE_TAG}"
IMAGE_NAME="$IMAGE_NAME" IMAGE_TAG="$IMAGE_TAG" docker compose build --pull

echo "镜像构建完成：${IMAGE_NAME}:${IMAGE_TAG}"
echo "镜像包含 Vite 生产构建产物，Python 服务将统一托管前端与 /api 接口。"
echo "启动命令：IMAGE_NAME=${IMAGE_NAME} IMAGE_TAG=${IMAGE_TAG} docker compose up -d"
