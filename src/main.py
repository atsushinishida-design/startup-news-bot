import requests
from bs4 import BeautifulSoup
from readability import Document
import os
import json
import time

# Slack通知用関数
def send_slack_message(message):
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    payload = {"text": message}
    requests.post(webhook_url, json=payload)

# 記事URLから本文を取得する関数
def fetch_article_text(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    html = r.text

    # readabilityで本文領域を推定
    doc = Document(html)
    content_html = doc.summary()

    soup = BeautifulSoup(content_html, "lxml")
    text = soup.get_text(separator="\n")
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
    return text[:4000]  # Slackのメッセージ制限（4000文字）

# 収集する記事のURLリスト
article_urls = [
    "https://prtimes.jp/main/html/rd/p/000000005.000145886.html",  # ここに実際のURLを追加
    "https://prtimes.jp/main/html/rd/p/000000028.000118467.html",
    "https://techblitz.com/startup-interview/allganize/",
    "https://thebridge.jp/2026/02/tashidelek-ecmile-funding-startup-factory",
    # 他のURLを追加
]

# メインの処理
def main():
    for url in article_urls:
        try:
            article_text = fetch_article_text(url)
            message = f"New article fetched: {url}\nTitle: {doc.title()}\n\n{article_text}"
            send_slack_message(message)
            print(f"Successfully sent to Slack: {url}")
            time.sleep(5)  # Slack APIに対するリクエスト間隔
        except Exception as e:
            print(f"Failed to fetch article from {url}: {e}")
            send_slack_message(f"Failed to fetch article from {url}: {str(e)}")

if __name__ == "__main__":
    main()
