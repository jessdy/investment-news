import json
import os
import sys
import unittest
from decimal import Decimal


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fetch_etf_shares  # noqa: E402


class FetchEtfSharesTest(unittest.TestCase):
    def test_parse_json_and_jsonp(self):
        expected = {"result": [{"SEC_CODE": "510050"}]}
        self.assertEqual(
            fetch_etf_shares.parse_json_payload(
                json.dumps(expected).encode("utf-8")
            ),
            expected,
        )
        self.assertEqual(
            fetch_etf_shares.parse_json_payload(
                ("callback(%s);" % json.dumps(expected)).encode("utf-8")
            ),
            expected,
        )

    def test_total_shares_conversion(self):
        shares_10k, total_shares = fetch_etf_shares.to_total_shares("8023282.05")
        self.assertEqual(shares_10k, Decimal("8023282.05"))
        self.assertEqual(total_shares, 80232820500)

    def test_rank_largest_uses_price_times_total_shares(self):
        rows = [
            {
                "STAT_DATE": "2026-07-24",
                "SEC_CODE": "510001",
                "SEC_NAME": "份额多",
                "TOT_VOL": "100",
            },
            {
                "STAT_DATE": "2026-07-24",
                "SEC_CODE": "510002",
                "SEC_NAME": "金额大",
                "TOT_VOL": "20",
            },
        ]
        quotes = {
            "510001": {
                "last": Decimal("1"),
                "previous_close": Decimal("0.9"),
                "expansion_abbr": "",
            },
            "510002": {
                "last": Decimal("10"),
                "previous_close": Decimal("9"),
                "expansion_abbr": "",
            },
        }
        ranked = fetch_etf_shares.rank_largest_by_amount(
            rows, "2026-07-24", quotes, 2
        )
        self.assertEqual(
            [item["fund_code"] for item in ranked],
            ["510002", "510001"],
        )
        self.assertEqual(ranked[0]["estimated_total_amount"], Decimal("2000000"))

    def test_rank_uses_previous_close_when_share_date_lags(self):
        rows = [{
            "STAT_DATE": "2026-07-24",
            "SEC_CODE": "510001",
            "TOT_VOL": "10",
        }]
        quotes = {
            "510001": {
                "last": Decimal("2"),
                "previous_close": Decimal("1.5"),
                "expansion_abbr": "",
            },
        }
        ranked = fetch_etf_shares.rank_largest_by_amount(
            rows, "2026-07-27", quotes, 1
        )
        self.assertEqual(ranked[0]["closing_price"], Decimal("1.5"))
        self.assertEqual(ranked[0]["ranking_date"], "2026-07-24")


if __name__ == "__main__":
    unittest.main()
