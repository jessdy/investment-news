#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MySQL 配置、连接与看板数据查询。"""
import json
import os
import re
from datetime import date

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


def _date_value(value, label):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError("%s必须是 YYYY-MM-DD 格式" % label)


def read_etf_share_data(start_date=None, end_date=None, default_days=30, max_days=90):
    """读取最新 ETF 规模排名，并按统一交易日轴返回份额与跟踪指数。"""
    requested_start = _date_value(start_date, "start_date")
    requested_end = _date_value(end_date, "end_date")
    if requested_start and requested_end and requested_start > requested_end:
        raise ValueError("start_date 不能晚于 end_date")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(ranking_date) AS ranking_date FROM etf_fund_rankings"
            )
            latest = cursor.fetchone()
            latest_date = latest["ranking_date"] if latest else None
            if latest_date is None:
                return {
                    "latest_date": "",
                    "range": {"start_date": "", "end_date": "", "trading_days": 0},
                    "items": [],
                }
            effective_end = requested_end or latest_date
            if requested_start:
                cursor.execute(
                    """
                    SELECT trade_date
                    FROM (
                        SELECT trade_date FROM etf_share_snapshots
                        WHERE trade_date BETWEEN %s AND %s
                        UNION
                        SELECT trade_date FROM etf_index_snapshots
                        WHERE trade_date BETWEEN %s AND %s
                    ) calendar
                    ORDER BY trade_date
                    """,
                    (requested_start, effective_end, requested_start, effective_end),
                )
                trading_dates = [row["trade_date"] for row in cursor.fetchall()]
                if len(trading_dates) > max_days:
                    raise ValueError("查询区间最多包含 %d 个交易日" % max_days)
            else:
                cursor.execute(
                    """
                    SELECT trade_date
                    FROM (
                        SELECT trade_date FROM etf_share_snapshots
                        WHERE trade_date <= %s
                        UNION
                        SELECT trade_date FROM etf_index_snapshots
                        WHERE trade_date <= %s
                    ) calendar
                    ORDER BY trade_date DESC
                    LIMIT %s
                    """,
                    (effective_end, effective_end, int(default_days)),
                )
                trading_dates = sorted(row["trade_date"] for row in cursor.fetchall())

            if not trading_dates:
                return {
                    "latest_date": latest_date.isoformat(),
                    "range": {"start_date": "", "end_date": "", "trading_days": 0},
                    "items": [],
                }
            effective_start, effective_end = trading_dates[0], trading_dates[-1]
            cursor.execute(
                """
                SELECT r.ranking_date, r.fund_code, r.fund_name,
                       r.fund_expansion_abbr, r.etf_type, r.amount_rank,
                       r.closing_price, r.total_shares, r.estimated_total_amount,
                       r.source_url, r.fetched_at,
                       COALESCE(m.benchmark_code, '') AS benchmark_code,
                       COALESCE(m.benchmark_name, '') AS benchmark_name,
                       COALESCE(m.is_supported, 0) AS benchmark_supported,
                       COALESCE(m.note, '尚未配置跟踪指数') AS benchmark_note
                FROM etf_fund_rankings r
                LEFT JOIN etf_benchmark_mappings m ON m.fund_code = r.fund_code
                WHERE r.ranking_date = %s
                ORDER BY r.amount_rank, r.fund_code
                """,
                (latest_date,),
            )
            items = cursor.fetchall()
            fund_codes = [row["fund_code"] for row in items]
            if not fund_codes:
                return {
                    "latest_date": latest_date.isoformat(),
                    "range": {
                        "start_date": effective_start.isoformat(),
                        "end_date": effective_end.isoformat(),
                        "trading_days": len(trading_dates),
                    },
                    "items": [],
                }
            placeholders = ",".join(["%s"] * len(fund_codes))
            cursor.execute(
                """
                SELECT trade_date, fund_code, total_shares, total_shares_10k
                FROM etf_share_snapshots
                WHERE fund_code IN (%s)
                  AND trade_date BETWEEN %%s AND %%s
                ORDER BY fund_code, trade_date
                """ % placeholders,
                fund_codes + [effective_start, effective_end],
            )
            history_rows = cursor.fetchall()
            benchmark_codes = sorted({
                row["benchmark_code"] for row in items if row["benchmark_code"]
            })
            index_rows = []
            if benchmark_codes:
                index_placeholders = ",".join(["%s"] * len(benchmark_codes))
                cursor.execute(
                    """
                    SELECT benchmark_code, trade_date, close_value
                    FROM etf_index_snapshots
                    WHERE benchmark_code IN (%s)
                      AND trade_date BETWEEN %%s AND %%s
                    ORDER BY benchmark_code, trade_date
                    """ % index_placeholders,
                    benchmark_codes + [effective_start, effective_end],
                )
                index_rows = cursor.fetchall()

    shares_by_fund = {}
    for row in history_rows:
        shares_by_fund.setdefault(row["fund_code"], {})[row["trade_date"]] = row
    index_by_code = {}
    for row in index_rows:
        index_by_code.setdefault(row["benchmark_code"], {})[row["trade_date"]] = row

    result_items = []
    for row in items:
        fund_shares = shares_by_fund.get(row["fund_code"], {})
        benchmark_values = index_by_code.get(row["benchmark_code"], {})
        history = []
        for trade_date in trading_dates:
            share = fund_shares.get(trade_date)
            index = benchmark_values.get(trade_date)
            history.append({
                "date": trade_date.isoformat(),
                "total_shares": str(share["total_shares"]) if share else None,
                "total_shares_10k": str(share["total_shares_10k"]) if share else None,
                "index_close": str(index["close_value"]) if index else None,
            })
        result_items.append({
            "date": row["ranking_date"].isoformat(),
            "fund_code": row["fund_code"],
            "fund_name": row["fund_name"],
            "fund_expansion_abbr": row["fund_expansion_abbr"],
            "etf_type": row["etf_type"],
            "rank": row["amount_rank"],
            "closing_price": str(row["closing_price"]),
            "total_shares": str(row["total_shares"]),
            "estimated_total_amount": str(row["estimated_total_amount"]),
            "source_url": row["source_url"],
            "fetched_at": row["fetched_at"].isoformat(timespec="seconds"),
            "benchmark": {
                "code": row["benchmark_code"],
                "name": row["benchmark_name"],
                "supported": bool(row["benchmark_supported"]),
                "note": row["benchmark_note"],
            },
            "history": history,
        })
    return {
        "latest_date": latest_date.isoformat(),
        "range": {
            "start_date": effective_start.isoformat(),
            "end_date": effective_end.isoformat(),
            "trading_days": len(trading_dates),
            "max_trading_days": max_days,
        },
        "items": result_items,
    }
