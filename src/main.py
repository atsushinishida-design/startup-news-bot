import os
import time
import json
import yaml
import feedparser
import requests
from openai import OpenAI
from utils import make_compass_url

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

INDUSTRY_LIST = [
    "通信・ネットワーキング", "コンピュータ", "半導体/その他電子部品・製品",
    "バイオテクノロジー", "医療・ヘルスケア", "産業・エネルギー", "環境",
    "消費者向けサービス・販売", "金融・保険・不動産", "ビジネスサービス"
]

def load_sources(path="config/sources.yml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)["sources"]

def fetch_rss(feed_url, max_items=20):
    feed = feedparser.parse(feed_url)
    articles = []
    for entry in feed.entries[:max_items]:
        articles.append({
            "url": getattr(entry, "link", ""),
            "title": getattr(entry, "title", ""),
            "summary": getattr(entry, "summary", ""),
        })
    return articles

def analyze_article(title: str, summary: str):
    prompt = f"""
以下はスタートアップ系メディアの記事タイトルと概要です。

タイトル: {title}
概要: {summary}

次の情報をJSON形式で返してください（余分な説明不要）:
{{
  "is_startup": true,
  "company_name": "会社名（不明な場合は空文字）",
  "industry": "以下のいずれか: {', '.join(INDUSTRY_LIST)}",
  "summary_50": "記事の要約（50字以内）"
}}

判定基準:
- 日本の会社、または創業者・主要メンバーが日本人の海外スタートアップならis_startup=true
- 大企業・上場企業・官公庁はis_startup=false
- スタートアップ・ベンチャー・新興企業はtrue
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"GPT error: {e}")
        return None

def send_slack(message: str):
    requests.post(SLACK_WEBHOOK_URL, json={"text": message})

def main():
    sources = load_sources()
    sent_count = 0

    for source in sources:
        print(f"Fetching: {source['name']}")
        articles = fetch_rss(source["feed_url"], source.get("max_items", 20))

        for article in articles:
            title = article["title"]
            summary = article["summary"][:500]
            url = article["url"]

            result = analyze_article(title, summary)
            if not result or not result.get("is_startup"):
                continue

            company = result.get("company_name", "")
            industry = result.get("industry", "不明")
            summary_50 = result.get("summary_50", "")
            compass_url = make_compass_url(company) if company else "（会社名不明）"

            message = (
                f"*[{source['name']}] {company or '（会社名不明）'}*\n"
                f"> {summary_50}\n"
                f"産業分類: {industry}\n"
                f"記事URL: {url}\n"
                f"社内DB検索: {compass_url}"
            )
            send_slack(message)
            sent_count += 1
            time.sleep(1)

    send_slack(f"Startup News Bot 完了: {sent_count}件送信")

if __name__ == "__main__":
    main()
