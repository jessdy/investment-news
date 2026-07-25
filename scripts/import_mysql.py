#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建 MySQL 表，并将 data.js / wechat-articles.js 导入数据库。"""
import argparse
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from database import connect  # noqa: E402


SCHEMA = """
CREATE TABLE IF NOT EXISTS app_metadata (
    meta_key VARCHAR(64) PRIMARY KEY,
    meta_value TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS industries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sector_key VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    accent VARCHAR(32) NOT NULL,
    source_total INT NOT NULL DEFAULT 0,
    sort_order INT NOT NULL DEFAULT 0,
    INDEX idx_industries_sort (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS news_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    industry_id BIGINT UNSIGNED NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_label VARCHAR(32) NOT NULL DEFAULT '',
    published_ts BIGINT NOT NULL DEFAULT 0,
    summary TEXT NOT NULL,
    source VARCHAR(255) NOT NULL DEFAULT '',
    title_zh TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    INDEX idx_news_industry_sort (industry_id, sort_order),
    CONSTRAINT fk_news_industry FOREIGN KEY (industry_id)
        REFERENCES industries(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS digest_points (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    industry_id BIGINT UNSIGNED NOT NULL,
    point_text TEXT NOT NULL,
    url TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    INDEX idx_digest_industry_sort (industry_id, sort_order),
    CONSTRAINT fk_digest_industry FOREIGN KEY (industry_id)
        REFERENCES industries(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS wechat_config (
    id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL,
    account_identifier VARCHAR(255) NOT NULL DEFAULT '',
    tagline TEXT NOT NULL,
    description TEXT NOT NULL,
    qr_image TEXT NOT NULL,
    source_album TEXT NOT NULL,
    imported_at VARCHAR(64) NOT NULL DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS wechat_articles (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    url TEXT NOT NULL,
    article_date VARCHAR(10) NOT NULL DEFAULT '',
    date_label VARCHAR(32) NOT NULL DEFAULT '',
    category VARCHAR(128) NOT NULL DEFAULT '',
    read_time VARCHAR(64) NOT NULL DEFAULT '',
    cover TEXT NOT NULL,
    article_order INT NOT NULL DEFAULT 0,
    featured TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_wechat_order (article_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def parse_javascript_data(path):
    with open(path, encoding="utf-8") as data_file:
        content = data_file.read()
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("%s 中未找到 JSON 对象" % path)
    return json.loads(content[start:end + 1])


def create_schema(cursor):
    for statement in SCHEMA.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def import_news(cursor, payload):
    cursor.execute("DELETE FROM digest_points")
    cursor.execute("DELETE FROM news_items")
    cursor.execute("DELETE FROM industries")
    cursor.execute("DELETE FROM app_metadata")

    stats = payload.get("stats") or {}
    metadata = {
        "generated_at": payload.get("generated_at", ""),
        "recent_days": payload.get("recent_days", 0),
        "industry_count": stats.get("industries", len(payload.get("industries") or [])),
        "total_sources": stats.get("total_sources", 0),
        "has_ai": str(bool(payload.get("has_ai"))).lower(),
    }
    cursor.executemany(
        "INSERT INTO app_metadata (meta_key, meta_value) VALUES (%s, %s)",
        [(key, str(value)) for key, value in metadata.items()],
    )

    for industry_order, industry in enumerate(payload.get("industries") or []):
        cursor.execute(
            """
            INSERT INTO industries
                (sector_key, name, accent, source_total, sort_order)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                industry.get("key", ""),
                industry.get("name", ""),
                industry.get("accent", ""),
                industry.get("total", 0),
                industry_order,
            ),
        )
        industry_id = cursor.lastrowid
        items = []
        for item_order, item in enumerate(industry.get("items") or []):
            items.append((
                industry_id,
                item.get("title", ""),
                item.get("url", ""),
                item.get("time", ""),
                item.get("ts", 0) or 0,
                item.get("summary", ""),
                item.get("source", ""),
                item.get("zh", ""),
                item_order,
            ))
        if items:
            cursor.executemany(
                """
                INSERT INTO news_items
                    (industry_id, title, url, published_label, published_ts,
                     summary, source, title_zh, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                items,
            )
        points = []
        for point_order, point in enumerate(industry.get("points") or []):
            if isinstance(point, str):
                text, url = point, ""
            else:
                text, url = point.get("t", ""), point.get("url", "")
            points.append((industry_id, text, url, point_order))
        if points:
            cursor.executemany(
                """
                INSERT INTO digest_points
                    (industry_id, point_text, url, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                points,
            )


def import_wechat(cursor, payload):
    cursor.execute("DELETE FROM wechat_articles")
    cursor.execute("DELETE FROM wechat_config")
    cursor.execute(
        """
        INSERT INTO wechat_config
            (id, account_name, account_identifier, tagline, description,
             qr_image, source_album, imported_at)
        VALUES (1, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            payload.get("accountName", ""),
            payload.get("accountId", ""),
            payload.get("tagline", ""),
            payload.get("description", ""),
            payload.get("qrImage", ""),
            payload.get("sourceAlbum", ""),
            payload.get("importedAt", ""),
        ),
    )
    articles = []
    for article in payload.get("articles") or []:
        articles.append((
            article.get("title", ""),
            article.get("summary", ""),
            article.get("url", ""),
            article.get("date", ""),
            article.get("dateLabel", ""),
            article.get("category", ""),
            article.get("readTime", ""),
            article.get("cover", ""),
            article.get("order", 0),
            int(bool(article.get("featured"))),
        ))
    if articles:
        cursor.executemany(
            """
            INSERT INTO wechat_articles
                (title, summary, url, article_date, date_label, category,
                 read_time, cover, article_order, featured)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            articles,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--news-only",
        action="store_true",
        help="仅同步 data.js，供后台定时刷新调用",
    )
    args = parser.parse_args()
    news = parse_javascript_data(os.environ.get("DATA_FILE", os.path.join(ROOT, "data.js")))
    wechat = None
    if not args.news_only:
        wechat = parse_javascript_data(os.path.join(ROOT, "wechat-articles.js"))

    with connect() as connection:
        try:
            with connection.cursor() as cursor:
                create_schema(cursor)
                import_news(cursor, news)
                if wechat is not None:
                    import_wechat(cursor, wechat)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    print(
        "MySQL 导入完成：%d 个行业%s"
        % (len(news.get("industries") or []), "" if wechat is None else "，%d 篇公众号文章" % len(wechat.get("articles") or []))
    )


if __name__ == "__main__":
    main()
