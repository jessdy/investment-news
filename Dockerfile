FROM node:22-bookworm-slim AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts ./
COPY src ./src
COPY docs/shengcai-youdao-qr.jpg ./docs/shengcai-youdao-qr.jpg
RUN npm run build

FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    HOST=0.0.0.0 \
    PORT=8793

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --create-home app

WORKDIR /app
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
COPY --from=frontend --chown=app:app /build/dist ./dist
RUN mkdir -p /app/runtime && chown app:app /app/runtime

USER app
EXPOSE 8793

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8793')+'/api/refresh-status',timeout=3).read()"]

CMD ["python", "server.py"]
