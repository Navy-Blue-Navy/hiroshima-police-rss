import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from pathlib import Path
import hashlib
import re
from datetime import datetime

URL = "https://www.pref.hiroshima.lg.jp/site/police/kensu.html"

# RSSファイルは、このPythonファイルと同じ場所に作る
OUTPUT = Path(__file__).parent / "hiroshima_police.xml"

# 県警ページを取得
response = requests.get(URL, timeout=30)
response.raise_for_status()
response.encoding = response.apparent_encoding

soup = BeautifulSoup(response.text, "html.parser")

# ページタイトル取得
page_title = soup.title.get_text(strip=True) if soup.title else ""

# 「10月5日（月曜日）」のような日付部分を取得
date_match = re.search(r"(\d{1,2})月(\d{1,2})日", page_title)

if date_match:
    month = int(date_match.group(1))
    day = int(date_match.group(2))

    now = datetime.now()
    year = now.year

    # 年末年始対策
    if now.month == 1 and month == 12:
        year -= 1

    info_date = f"{year}-{month:02d}-{day:02d}"
else:
    info_date = datetime.now().strftime("%Y-%m-%d")

# 現在掲載されている事件を取得
new_items = []

for heading in soup.find_all(["h3", "h4"]):
    title = heading.get_text(" ", strip=True)

    if not title:
        continue

    text = ""
    next_element = heading.find_next_sibling()

    while next_element:
        if next_element.name in ["h2", "h3", "h4"]:
            break

        if next_element.name == "p":
            part = next_element.get_text(" ", strip=True)
            if part:
                text += part

        next_element = next_element.find_next_sibling()

    if not text:
        continue

    # 同じ事件を識別するための固有ID
    raw_id = info_date + "|" + title + "|" + text
    guid = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

    new_items.append({
        "title": title,
        "description": text,
        "date": info_date,
        "guid": guid
    })

# 以前のRSSに入っている事件を読み込む
old_items = []

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)
        old_root = old_tree.getroot()

        for item in old_root.findall("./channel/item"):
            old_items.append({
                "title": item.findtext("title", ""),
                "description": item.findtext("description", ""),
                "date": item.findtext("pubDate", ""),
                "guid": item.findtext("guid", "")
            })
    except Exception:
        old_items = []

# 新旧を合体し、重複を除く
all_items = []
seen = set()

for item in new_items + old_items:
    if item["guid"] in seen:
        continue

    seen.add(item["guid"])
    all_items.append(item)

# RSSが大きくなりすぎないよう最新300件を保存
all_items = all_items[:300]

# RSS作成
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "広島県警 事件発生・逮捕情報"
ET.SubElement(channel, "link").text = URL
ET.SubElement(channel, "description").text = "広島県警察が公表する事件発生・逮捕情報"
ET.SubElement(channel, "language").text = "ja"

for item in all_items:
    element = ET.SubElement(channel, "item")

    ET.SubElement(element, "title").text = item["title"]
    ET.SubElement(element, "link").text = URL
    ET.SubElement(element, "description").text = item["description"]
    ET.SubElement(element, "pubDate").text = item["date"]

    guid_element = ET.SubElement(element, "guid")
    guid_element.set("isPermaLink", "false")
    guid_element.text = item["guid"]

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

print("RSS作成成功")
print("今回取得:", len(new_items), "件")
print("RSS保存件数:", len(all_items), "件")
print("対象日:", info_date)
print("保存先:", OUTPUT)