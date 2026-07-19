#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从浏览器保存的微信公众号合集 HTML 导入文章列表。"""
import argparse
import html
import json
import os
import re
from datetime import datetime
from html.parser import HTMLParser


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AlbumParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None
        self.in_time = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "li" and "js_album_item" in classes and attrs.get("data-link"):
            self.current = {
                "title": attrs.get("data-title", "").strip(),
                "url": html.unescape(attrs.get("data-link", "").strip()).replace("http://", "https://", 1),
                "dateLabel": "",
                "cover": "",
            }
        if self.current and "js_article_create_time" in classes:
            self.in_time = True
        if self.current and "album__item-img" in classes:
            match = re.search(r"url\(([^)]+)\)", attrs.get("style", ""))
            if match:
                self.current["cover"] = match.group(1).strip("\"'")

    def handle_data(self, data):
        if self.current and self.in_time:
            self.current["dateLabel"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "span" and self.in_time:
            self.in_time = False
        if tag == "li" and self.current:
            self.items.append(self.current)
            self.current = None
            self.in_time = False


def category_for(title):
    rules = [
        ("机器人", ("机器人", "丝杠", "钕铁硼")),
        ("光通信", ("CPO", "光纤", "光模块", "波导", "铌酸锂", "磷化铟", "铜缆")),
        ("半导体材料", ("光刻胶", "靶材", "抛光", "石英", "氦气", "氢氟酸", "前驱体", "氧化铝", "电子布", "PPO", "PSPI", "MUF", "ABF")),
        ("芯片与封装", ("芯片", "封装", "键合", "基板", "载板", "TGV", "硅片", "封测", "HBM", "DRAM", "存储", "MLCC", "CIS")),
        ("AI 算力", ("AI", "英伟达", "算力", "服务器")),
        ("市场观察", ("A股", "指数", "涨停", "暴涨", "暴跌", "科技", "行情", "板块", "接棒", "反攻", "点火")),
    ]
    for category, keywords in rules:
        if any(word.lower() in title.lower() for word in keywords):
            return category
    return "产业观察"


def main():
    parser = argparse.ArgumentParser(description="导入微信公众号合集 HTML")
    parser.add_argument("html_file", help="浏览器保存的合集 HTML 文件")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="MM/DD 时间对应的年份")
    parser.add_argument("--output", default=os.path.join(ROOT, "wechat-articles.js"))
    args = parser.parse_args()

    album = AlbumParser()
    with open(args.html_file, encoding="utf-8") as source:
        album.feed(source.read())

    seen, articles = set(), []
    for order, item in enumerate(album.items, 1):
        if not item["title"] or item["url"] in seen:
            continue
        seen.add(item["url"])
        match = re.fullmatch(r"(\d{2})/(\d{2})", item["dateLabel"])
        date = "%04d-%s-%s" % (args.year, match.group(1), match.group(2)) if match else ""
        articles.append({
            "title": item["title"],
            "summary": "来自“生财佑道”公众号产业分析合集，点击阅读完整文章。",
            "url": item["url"],
            "date": date,
            "dateLabel": item["dateLabel"],
            "category": category_for(item["title"]),
            "readTime": "公众号原文",
            "cover": item["cover"],
            "order": order,
            "featured": False,
        })

    if articles:
        articles[-1]["featured"] = True

    data = {
        "accountName": "生财佑道",
        "accountId": "",
        "tagline": "关注 AI、机器人与产业智能的长期趋势",
        "description": "从产业链、技术演进和商业落地三个视角，提供有判断、有依据的深度内容。",
        "qrImage": "docs/shengcai-youdao-qr.jpg",
        "sourceAlbum": "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzAxNDY3MjIxNA==&action=getalbum&album_id=4530522308145840130",
        "importedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "articles": articles,
    }
    with open(args.output, "w", encoding="utf-8") as target:
        target.write("// 由 scripts/import_wechat_album.py 从微信公众号合集页面生成。\n")
        target.write("window.WECHAT_CONTENT = ")
        json.dump(data, target, ensure_ascii=False, indent=2)
        target.write(";\n")
    print("已导入 %d 篇文章 → %s" % (len(articles), args.output))


if __name__ == "__main__":
    main()
