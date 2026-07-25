#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MySQL 配置、连接与看板数据查询。"""
import json
import os
import re

import pymysql
from pymysql.cursors import DictCursor


HERE = os.path.dirname(os.path.abspath(__file__))


def load_dotenv():
    """加载项目根目录 .env；已有系统环境变量优先。"""
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for raw in env_file:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                continue
            if len(value) >= 2 and value[0] == value[-1] == '"':
                try:
                    value = json.loads(value)
                except (TypeError, ValueError):
                    value = value[1:-1]
            elif len(value) >= 2 and value[0] == value[-1] == "'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


def database_config():
    load_dotenv()
    required = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("缺少数据库配置：" + ", ".join(missing))
    return {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.environ["MYSQL_DATABASE"],
        "charset": "utf8mb4",
        "connect_timeout": int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "10")),
        "read_timeout": int(os.environ.get("MYSQL_READ_TIMEOUT", "20")),
        "write_timeout": int(os.environ.get("MYSQL_WRITE_TIMEOUT", "20")),
        "autocommit": False,
        "cursorclass": DictCursor,
    }


def connect():
    return pymysql.connect(**database_config())


def read_news_data():
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT meta_key, meta_value FROM app_metadata")
            metadata = {row["meta_key"]: row["meta_value"] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT id, sector_key, name, accent, source_total
                FROM industries
                ORDER BY sort_order, id
                """
            )
            industries = cursor.fetchall()
            cursor.execute(
                """
                SELECT industry_id, title, url, published_label, published_ts,
                       summary, source, title_zh
                FROM news_items
                ORDER BY industry_id, sort_order, id
                """
            )
            news_items = cursor.fetchall()
            cursor.execute(
                """
                SELECT industry_id, point_text, url
                FROM digest_points
                ORDER BY industry_id, sort_order, id
                """
            )
            digest_points = cursor.fetchall()

    items_by_industry = {}
    for row in news_items:
        items_by_industry.setdefault(row["industry_id"], []).append({
            "title": row["title"],
            "url": row["url"],
            "time": row["published_label"],
            "ts": row["published_ts"],
            "summary": row["summary"],
            "source": row["source"],
            "zh": row["title_zh"],
        })
    points_by_industry = {}
    for row in digest_points:
        points_by_industry.setdefault(row["industry_id"], []).append({
            "t": row["point_text"],
            "url": row["url"],
        })

    result_industries = []
    for industry in industries:
        result_industries.append({
            "key": industry["sector_key"],
            "name": industry["name"],
            "accent": industry["accent"],
            "total": industry["source_total"],
            "items": items_by_industry.get(industry["id"], []),
            "points": points_by_industry.get(industry["id"], []),
        })
    return {
        "generated_at": metadata.get("generated_at", ""),
        "recent_days": int(metadata.get("recent_days", "0")),
        "industries": result_industries,
        "stats": {
            "industries": int(metadata.get("industry_count", str(len(result_industries)))),
            "total_sources": int(metadata.get("total_sources", "0")),
        },
        "has_ai": metadata.get("has_ai", "false").lower() == "true",
    }


def read_wechat_content():
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM wechat_config WHERE id = 1")
            config = cursor.fetchone()
            cursor.execute(
                """
                SELECT title, summary, url, article_date, date_label, category,
                       read_time, cover, article_order, featured
                FROM wechat_articles
                ORDER BY article_order, id
                """
            )
            articles = cursor.fetchall()
    if not config:
        return {"accountName": "", "articles": []}
    return {
        "accountName": config["account_name"],
        "accountId": config["account_identifier"],
        "tagline": config["tagline"],
        "description": config["description"],
        "qrImage": config["qr_image"],
        "sourceAlbum": config["source_album"],
        "importedAt": config["imported_at"],
        "articles": [{
            "title": row["title"],
            "summary": row["summary"],
            "url": row["url"],
            "date": row["article_date"],
            "dateLabel": row["date_label"],
            "category": row["category"],
            "readTime": row["read_time"],
            "cover": row["cover"],
            "order": row["article_order"],
            "featured": bool(row["featured"]),
        } for row in articles],
    }
