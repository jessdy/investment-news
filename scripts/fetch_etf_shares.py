#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按场内总金额选出上交所最大的 ETF，记录它们最近 10 个交易日总份额。

场内总金额估算口径：
    上交所最新收盘价 × 同日基金总份额

总份额及历史数据来自基金详情页“基金规模”栏目使用的公开查询接口。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

QUERY_URL = "https://query.sse.com.cn/commonQuery.do"
QUOTE_URL = "https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/ebs"
DETAIL_PAGE = (
    "https://www.sse.com.cn/assortment/fund/list/etfinfo/basic/"
    "index.shtml?FUNDID={code}"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TOP_LIST_SQL_ID = "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L"
DETAIL_SQL_ID = "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L"

SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_fund_rankings (
    ranking_date DATE NOT NULL,
    fund_code CHAR(6) NOT NULL,
    fund_name VARCHAR(255) NOT NULL,
    fund_expansion_abbr VARCHAR(255) NOT NULL DEFAULT '',
    etf_type VARCHAR(32) NOT NULL DEFAULT '',
    amount_rank SMALLINT UNSIGNED NOT NULL,
    closing_price DECIMAL(16,4) NOT NULL,
    total_shares BIGINT UNSIGNED NOT NULL,
    estimated_total_amount DECIMAL(28,2) NOT NULL,
    source_url TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ranking_date, fund_code),
    UNIQUE KEY uk_etf_ranking_date_rank (ranking_date, amount_rank)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS etf_share_snapshots (
    trade_date DATE NOT NULL,
    fund_code CHAR(6) NOT NULL,
    fund_name VARCHAR(255) NOT NULL,
    fund_expansion_abbr VARCHAR(255) NOT NULL DEFAULT '',
    etf_type VARCHAR(32) NOT NULL DEFAULT '',
    total_shares BIGINT UNSIGNED NOT NULL,
    total_shares_10k DECIMAL(24,2) NOT NULL,
    source_url TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, fund_code),
    INDEX idx_etf_snapshot_fund_date (fund_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def parse_json_payload(raw):
    """兼容 JSON 与 JSONP 响应。"""
    text = raw.decode("utf-8-sig").strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.fullmatch(r"[A-Za-z_$][\w$]*\((.*)\);?", text, re.S)
    if not match:
        raise ValueError("上交所接口返回了无法识别的内容")
    return json.loads(match.group(1))


def request_url_json(url, params, referer, retries=3, timeout=20):
    request = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={
            "Accept": "application/json,text/javascript,*/*;q=0.01",
            "Referer": referer,
            "User-Agent": USER_AGENT,
        },
    )
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = parse_json_payload(response.read())
            if payload.get("actionErrors"):
                raise RuntimeError("；".join(payload["actionErrors"]))
            return payload
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("上交所接口请求失败：%s" % last_error)


def request_query(params, fund_code=""):
    return request_url_json(
        QUERY_URL,
        params,
        DETAIL_PAGE.format(code=fund_code or "510300"),
    )


def to_decimal(value, label):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("无效的%s：%r" % (label, value))
    if result < 0:
        raise ValueError("%s不能为负数：%s" % (label, value))
    return result


def to_total_shares(value):
    """上交所万份数转换为实际份额数，保留其披露精度。"""
    shares_10k = to_decimal(value, "总份额")
    return shares_10k, int(shares_10k * Decimal("10000"))


def fetch_market_snapshot():
    payload = request_query({
        "isPagination": "true",
        "sqlId": TOP_LIST_SQL_ID,
        "pageHelp.pageSize": "2000",
        "pageHelp.cacheSize": "1",
        "STAT_DATE": "",
    })
    rows = payload.get("result") or []
    if not rows:
        raise RuntimeError("上交所未返回最新交易日 ETF 规模数据")
    return rows


def fetch_quotes():
    payload = request_url_json(
        QUOTE_URL,
        {"select": "code,name,last,prev_close,cpxxextendname"},
        "https://www.sse.com.cn/assortment/fund/list/etfinfo/price/",
    )
    quote_date = str(payload.get("date") or "")
    if not re.fullmatch(r"\d{8}", quote_date):
        raise RuntimeError("上交所行情接口未返回有效日期")
    quotes = {}
    for values in payload.get("list") or []:
        if len(values) < 4:
            continue
        code = str(values[0])
        try:
            last = to_decimal(values[2], "最新价格")
            previous_close = to_decimal(values[3], "前收盘价")
        except ValueError:
            continue
        if re.fullmatch(r"\d{6}", code) and (last > 0 or previous_close > 0):
            quotes[code] = {
                "last": last,
                "previous_close": previous_close,
                "expansion_abbr": str(values[4] or "") if len(values) > 4 else "",
            }
    return (
        "%s-%s-%s" % (quote_date[:4], quote_date[4:6], quote_date[6:]),
        quotes,
    )


def rank_largest_by_amount(scale_rows, quote_date, quotes, limit):
    ranked = []
    for row in scale_rows:
        code = str(row.get("SEC_CODE") or "")
        quote = quotes.get(code)
        scale_date = row.get("STAT_DATE")
        if quote is None or not scale_date:
            continue
        # 盘中份额数据仍停留在上一交易日，此时用前收盘价与份额日期对齐。
        if scale_date == quote_date:
            price = quote["last"] or quote["previous_close"]
        elif scale_date < quote_date:
            price = quote["previous_close"]
        else:
            continue
        if price <= 0:
            continue
        try:
            shares_10k, total_shares = to_total_shares(row.get("TOT_VOL"))
        except ValueError:
            continue
        amount = Decimal(total_shares) * price
        ranked.append({
            "ranking_date": scale_date,
            "fund_code": code,
            "fund_name": str(row.get("SEC_NAME") or ""),
            "fund_expansion_abbr": quote["expansion_abbr"],
            "etf_type": str(row.get("ETF_TYPE") or ""),
            "closing_price": price,
            "total_shares": total_shares,
            "estimated_total_amount": amount,
            "source_url": DETAIL_PAGE.format(code=code),
        })
    ranked.sort(
        key=lambda row: (-row["estimated_total_amount"], row["fund_code"])
    )
    for rank, row in enumerate(ranked[:limit], 1):
        row["amount_rank"] = rank
    return ranked[:limit]


def fetch_share_history(fund):
    payload = request_query(
        {
            "isPagination": "true",
            "sqlId": DETAIL_SQL_ID,
            "SEC_CODE": fund["fund_code"],
            "pageHelp.pageSize": "10",
        },
        fund_code=fund["fund_code"],
    )
    result = []
    for row in (payload.get("result") or [])[:10]:
        try:
            shares_10k, total_shares = to_total_shares(row.get("TOT_VOL"))
        except ValueError:
            continue
        result.append({
            "trade_date": row.get("STAT_DATE"),
            "fund_code": fund["fund_code"],
            "fund_name": str(row.get("SEC_NAME") or fund["fund_name"]),
            "fund_expansion_abbr": str(
                row.get("FUND_EXPANSION_ABBR")
                or fund["fund_expansion_abbr"]
            ),
            "etf_type": str(row.get("ETF_TYPE") or fund["etf_type"]),
            "total_shares": total_shares,
            "total_shares_10k": format(shares_10k, "f"),
            "source_url": fund["source_url"],
        })
    if len(result) != 10:
        raise RuntimeError(
            "%s 最近份额数据不足 10 天：%d"
            % (fund["fund_code"], len(result))
        )
    return result


def collect_top_etfs(limit=10):
    scale_rows = fetch_market_snapshot()
    quote_date, quotes = fetch_quotes()
    rankings = rank_largest_by_amount(scale_rows, quote_date, quotes, limit)
    if len(rankings) < limit:
        raise RuntimeError(
            "同日有效 ETF 数量不足：期望 %d，实际 %d"
            % (limit, len(rankings))
        )
    with ThreadPoolExecutor(max_workers=5) as executor:
        histories = list(executor.map(fetch_share_history, rankings))
    snapshots = [row for history in histories for row in history]
    return rankings, snapshots


def fetch_backfill_date(stat_date, funds):
    payload = request_query({
        "isPagination": "true",
        "sqlId": TOP_LIST_SQL_ID,
        "pageHelp.pageSize": "2000",
        "pageHelp.cacheSize": "1",
        "STAT_DATE": stat_date,
    })
    rows_by_code = {
        str(row.get("SEC_CODE")): row
        for row in payload.get("result") or []
    }
    if not rows_by_code:
        return []
    result = []
    for code, fund in funds.items():
        row = rows_by_code.get(code)
        if row is None:
            raise RuntimeError("%s 在 %s 缺少份额数据" % (code, stat_date))
        shares_10k, total_shares = to_total_shares(row.get("TOT_VOL"))
        result.append({
            "trade_date": stat_date,
            "fund_code": code,
            "fund_name": str(row.get("SEC_NAME") or fund["fund_name"]),
            "fund_expansion_abbr": fund["fund_expansion_abbr"],
            "etf_type": str(row.get("ETF_TYPE") or fund["etf_type"]),
            "total_shares": total_shares,
            "total_shares_10k": format(shares_10k, "f"),
            "source_url": fund["source_url"],
        })
    return result


def load_latest_ranked_funds():
    from database import connect

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT MAX(ranking_date) AS date FROM etf_fund_rankings")
            latest = cursor.fetchone()
            ranking_date = latest["date"] if latest else None
            if ranking_date is None:
                raise RuntimeError("数据库中还没有 ETF 金额排名")
            cursor.execute(
                """
                SELECT fund_code, fund_name, fund_expansion_abbr,
                       etf_type, source_url
                FROM etf_fund_rankings
                WHERE ranking_date = %s
                ORDER BY amount_rank
                """,
                (ranking_date,),
            )
            rows = cursor.fetchall()
    return {row["fund_code"]: row for row in rows}


def collect_backfill(funds, before_date, days):
    before = datetime.strptime(before_date, "%Y-%m-%d").date()
    snapshots = []
    offset = 1
    while len({row["trade_date"] for row in snapshots}) < days:
        candidates = [
            (before - timedelta(days=offset + index)).isoformat()
            for index in range(14)
        ]
        with ThreadPoolExecutor(max_workers=5) as executor:
            batches = list(executor.map(
                lambda date: fetch_backfill_date(date, funds),
                candidates,
            ))
        for batch in batches:
            if batch:
                snapshots.extend(batch)
                if len({row["trade_date"] for row in snapshots}) >= days:
                    break
        offset += len(candidates)
        if offset > days * 4 + 31:
            raise RuntimeError("无法找到足够的历史交易日")
    selected_dates = sorted(
        {row["trade_date"] for row in snapshots},
        reverse=True,
    )[:days]
    selected = [
        row for row in snapshots if row["trade_date"] in selected_dates
    ]
    selected.sort(key=lambda row: (row["trade_date"], row["fund_code"]))
    return selected


def create_schema(cursor):
    cursor.execute("SHOW TABLES LIKE 'etf_share_snapshots'")
    if cursor.fetchone():
        cursor.execute("SHOW COLUMNS FROM etf_share_snapshots")
        columns = {row["Field"] for row in cursor.fetchall()}
        if "daily_rank" in columns:
            # 旧表按总份额排名，口径错误；删除后按新模型重建。
            cursor.execute("DROP TABLE etf_share_snapshots")
    for statement in SCHEMA.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def save_data(rankings, snapshots):
    from database import connect

    with connect() as connection:
        try:
            with connection.cursor() as cursor:
                create_schema(cursor)
                ranking_date = rankings[0]["ranking_date"]
                cursor.execute(
                    "DELETE FROM etf_fund_rankings WHERE ranking_date = %s",
                    (ranking_date,),
                )
                cursor.executemany(
                    """
                    INSERT INTO etf_fund_rankings
                        (ranking_date, fund_code, fund_name,
                         fund_expansion_abbr, etf_type, amount_rank,
                         closing_price, total_shares,
                         estimated_total_amount, source_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [(
                        row["ranking_date"], row["fund_code"],
                        row["fund_name"], row["fund_expansion_abbr"],
                        row["etf_type"], row["amount_rank"],
                        str(row["closing_price"]), row["total_shares"],
                        str(row["estimated_total_amount"]), row["source_url"],
                    ) for row in rankings],
                )
                cursor.executemany(
                    """
                    INSERT INTO etf_share_snapshots
                        (trade_date, fund_code, fund_name,
                         fund_expansion_abbr, etf_type, total_shares,
                         total_shares_10k, source_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        fund_name = VALUES(fund_name),
                        fund_expansion_abbr = VALUES(fund_expansion_abbr),
                        etf_type = VALUES(etf_type),
                        total_shares = VALUES(total_shares),
                        total_shares_10k = VALUES(total_shares_10k),
                        source_url = VALUES(source_url),
                        fetched_at = CURRENT_TIMESTAMP
                    """,
                    [(
                        row["trade_date"], row["fund_code"],
                        row["fund_name"], row["fund_expansion_abbr"],
                        row["etf_type"], row["total_shares"],
                        row["total_shares_10k"], row["source_url"],
                    ) for row in snapshots],
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def serializable(rankings, snapshots):
    ranking_rows = []
    by_code = {}
    for row in snapshots:
        by_code.setdefault(row["fund_code"], []).append(row)
    for fund in rankings:
        item = dict(fund)
        item["closing_price"] = format(item["closing_price"], "f")
        item["estimated_total_amount"] = format(
            item["estimated_total_amount"], "f"
        )
        item["history"] = by_code.get(item["fund_code"], [])
        ranking_rows.append(item)
    return ranking_rows


def main():
    parser = argparse.ArgumentParser(
        description="按总金额记录上交所最大 ETF 最近 10 天总份额"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=int(os.environ.get("ETF_TOP_N", "10")),
        help="记录前 N 名，默认 10",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅抓取并输出 JSON，不写入 MySQL",
    )
    args = parser.parse_args()
    if args.top < 1 or args.top > 100:
        parser.error("--top 必须在 1 到 100 之间")

    rankings, snapshots = collect_top_etfs(args.top)
    if args.dry_run:
        print(json.dumps(
            serializable(rankings, snapshots),
            ensure_ascii=False,
            indent=2,
        ))
        return
    save_data(rankings, snapshots)
    print(
        "ETF 金额排名与份额历史写入完成：%s，前 %d 名，每只 10 天"
        % (rankings[0]["ranking_date"], len(rankings))
    )
    for row in rankings:
        print(
            "  %02d  %s  %-18s  %.2f 亿元"
            % (
                row["amount_rank"],
                row["fund_code"],
                row["fund_expansion_abbr"] or row["fund_name"],
                row["estimated_total_amount"] / Decimal("100000000"),
            )
        )


if __name__ == "__main__":
    main()
