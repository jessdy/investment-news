#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使用 AkShare 采集上交所规模前十 ETF 的精确跟踪标的历史。

仅收录可由 AkShare 精确获得的跟踪标的；无法精确匹配时保留映射状态，
前端明确显示“指数暂不可用”，不使用相近指数替代。
"""
import argparse
import json
import math
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

import akshare as ak


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_benchmark_mappings (
    fund_code CHAR(6) NOT NULL,
    benchmark_code VARCHAR(32) NOT NULL DEFAULT '',
    benchmark_name VARCHAR(255) NOT NULL,
    adapter VARCHAR(32) NOT NULL DEFAULT '',
    symbol VARCHAR(64) NOT NULL DEFAULT '',
    is_supported TINYINT(1) NOT NULL DEFAULT 1,
    note VARCHAR(500) NOT NULL DEFAULT '',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (fund_code),
    INDEX idx_etf_benchmark_code (benchmark_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS etf_index_snapshots (
    benchmark_code VARCHAR(32) NOT NULL,
    trade_date DATE NOT NULL,
    benchmark_name VARCHAR(255) NOT NULL,
    close_value DECIMAL(24,8) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'akshare',
    fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (benchmark_code, trade_date),
    INDEX idx_etf_index_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


# 当前榜单基金的精确跟踪标的。中证/上证指数统一通过中证指数官网适配器获取。
# 511520 的精确“中债-7-10年政策性金融债全价(总值)指数”不在 AkShare
# 当前暴露的精确指数列表中，因此按产品约定显式标记为不可用。
DEFAULT_MAPPINGS = [
    ("510300", "000300", "沪深300指数", "csindex", "000300", 1, ""),
    ("510310", "000300", "沪深300指数", "csindex", "000300", 1, ""),
    ("518880", "AU9999", "国内黄金现货（Au99.99）", "sge", "Au99.99", 1, ""),
    ("511360", "H11014", "中证短融指数", "csindex", "H11014", 1, ""),
    ("588000", "000688", "上证科创板50成份指数", "csindex", "000688", 1, ""),
    ("511380", "931078", "中证可转债及可交换债券指数", "csindex", "931078", 1, ""),
    ("512880", "399975", "中证全指证券公司指数", "csindex", "399975", 1, ""),
    ("511220", "H11098", "上证城投债指数", "csindex", "H11098", 1, ""),
    ("588200", "000685", "上证科创板芯片指数", "csindex", "000685", 1, ""),
    (
        "511520",
        "",
        "中债-7-10年政策性金融债全价（总值）指数",
        "",
        "",
        0,
        "AkShare 暂无该精确指数接口，未使用近似指数替代",
    ),
]


def create_schema(cursor):
    for statement in SCHEMA.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def seed_mappings(cursor):
    cursor.executemany(
        """
        INSERT INTO etf_benchmark_mappings
            (fund_code, benchmark_code, benchmark_name, adapter, symbol,
             is_supported, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            benchmark_code = VALUES(benchmark_code),
            benchmark_name = VALUES(benchmark_name),
            adapter = VALUES(adapter),
            symbol = VALUES(symbol),
            is_supported = VALUES(is_supported),
            note = VALUES(note)
        """,
        DEFAULT_MAPPINGS,
    )
    cursor.execute(
        """
        INSERT IGNORE INTO etf_benchmark_mappings
            (fund_code, benchmark_name, is_supported, note)
        SELECT DISTINCT r.fund_code, CONCAT(r.fund_name, '跟踪指数'), 0,
               '榜单新增基金尚未配置精确跟踪指数'
        FROM etf_fund_rankings r
        LEFT JOIN etf_benchmark_mappings m ON m.fund_code = r.fund_code
        WHERE r.ranking_date = (SELECT MAX(ranking_date) FROM etf_fund_rankings)
          AND m.fund_code IS NULL
        """
    )


def latest_active_mappings(cursor):
    cursor.execute(
        """
        SELECT DISTINCT m.benchmark_code, m.benchmark_name, m.adapter, m.symbol
        FROM etf_benchmark_mappings m
        JOIN etf_fund_rankings r ON r.fund_code = m.fund_code
        WHERE r.ranking_date = (SELECT MAX(ranking_date) FROM etf_fund_rankings)
          AND m.is_supported = 1
          AND m.benchmark_code <> ''
        ORDER BY m.benchmark_code
        """
    )
    return cursor.fetchall()


def clean_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fetch_csindex(symbol, start_date, end_date):
    frame = ak.stock_zh_index_hist_csindex(
        symbol=symbol,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    rows = []
    for _, item in frame.iterrows():
        close = clean_number(item.get("收盘"))
        trade_date = item.get("日期")
        if close is None or not trade_date:
            continue
        rows.append((trade_date, close))
    return rows


def fetch_sge(symbol, start_date, end_date):
    frame = ak.spot_hist_sge(symbol=symbol)
    rows = []
    for _, item in frame.iterrows():
        trade_date = item.get("date")
        close = clean_number(item.get("close"))
        if close is None or not trade_date or not (start_date <= trade_date <= end_date):
            continue
        rows.append((trade_date, close))
    return rows


def fetch_mapping(mapping, start_date, end_date):
    adapter = mapping["adapter"]
    if adapter == "csindex":
        return fetch_csindex(mapping["symbol"], start_date, end_date)
    if adapter == "sge":
        return fetch_sge(mapping["symbol"], start_date, end_date)
    raise ValueError("不支持的 AkShare 适配器：%s" % adapter)


def save_rows(cursor, mapping, rows):
    cursor.executemany(
        """
        INSERT INTO etf_index_snapshots
            (benchmark_code, trade_date, benchmark_name, close_value)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            benchmark_name = VALUES(benchmark_name),
            close_value = VALUES(close_value),
            fetched_at = CURRENT_TIMESTAMP
        """,
        [
            (
                mapping["benchmark_code"],
                trade_date,
                mapping["benchmark_name"],
                format(Decimal(str(close)), "f"),
            )
            for trade_date, close in rows
        ],
    )


def collect(days=180, dry_run=False):
    from database import connect

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    with connect() as connection:
        with connection.cursor() as cursor:
            create_schema(cursor)
            seed_mappings(cursor)
            mappings = latest_active_mappings(cursor)
        connection.commit()

    results = []
    for mapping in mappings:
        try:
            rows = fetch_mapping(mapping, start_date, end_date)
            if not rows:
                raise RuntimeError("AkShare 未返回区间数据")
            if not dry_run:
                with connect() as connection:
                    with connection.cursor() as cursor:
                        save_rows(cursor, mapping, rows)
                    connection.commit()
            results.append({
                "benchmark_code": mapping["benchmark_code"],
                "benchmark_name": mapping["benchmark_name"],
                "ok": True,
                "rows": len(rows),
                "last_date": max(row[0] for row in rows).isoformat(),
            })
        except Exception as error:
            results.append({
                "benchmark_code": mapping["benchmark_code"],
                "benchmark_name": mapping["benchmark_name"],
                "ok": False,
                "error": str(error),
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="采集 ETF 精确跟踪指数历史")
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.environ.get("ETF_INDEX_FETCH_DAYS", "180")),
        help="回溯自然日数，默认 180",
    )
    parser.add_argument("--dry-run", action="store_true", help="采集并输出但不写入指数快照")
    args = parser.parse_args()
    if args.days < 30 or args.days > 3650:
        parser.error("--days 必须在 30 到 3650 之间")

    results = collect(args.days, args.dry_run)
    print(json.dumps({
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "ok": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
        "items": results,
    }, ensure_ascii=False))
    if results and not any(item["ok"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
