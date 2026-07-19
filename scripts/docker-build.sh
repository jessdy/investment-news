#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="${IMAGE_NAME:-investment-news}"
IMAGE_TAG="${1:-${IMAGE_TAG:-latest}}"

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

echo "正在构建镜像 ${IMAGE_NAME}:${IMAGE_TAG}"
IMAGE_NAME="$IMAGE_NAME" IMAGE_TAG="$IMAGE_TAG" docker compose build --pull

echo "镜像构建完成：${IMAGE_NAME}:${IMAGE_TAG}"
echo "启动命令：IMAGE_NAME=${IMAGE_NAME} IMAGE_TAG=${IMAGE_TAG} docker compose up -d"
