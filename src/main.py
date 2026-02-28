import requests
from bs4 import BeautifulSoup
from readability import Document  # 必ずインポート
import os
import json
import time
from playwright.sync_api import sync_playwright  # Playwrightのインポート
import spacy
from google import google  # Google検索API
import feedparser  # RSSフィード用ライブラリ

# spaCyの日本語モデルをロード
nlp = spacy.load('ja_core_news_sm')

# Slack通知用関数
def send_slack_message(message):
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    payload = {"text": message}
    requests.post(webhook_url, json=payload)

# 記事URLから本文を取得する関数（Playwrightでページを取得）
def fetch_article_text(url: str) -> str:
    # Playwrightを使ってブラウザでページを取得
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # headlessモードでブラウザ起動
        page = browser.new_page()

        # URLにアクセス
        page.goto(url)

        # ページのHTMLを取得
        html = page.content()
        browser.close()

    # Documentクラスを使って記事本文を抽出
    doc = Document(html)  # Documentのインスタンスを作成
    content_html = doc.summary()  # summaryメソッドで本文を抽出
    title = doc.title()  # 記事のタイトルを取得

    soup = BeautifulSoup(content_html, "lxml")
    text = soup.get_text(separator="\n")
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
    
    return title, text[:4000]  # タイトルと本文を返す

# 会社名の抽出関数
def extract_company_name(article_text):
    doc = nlp(article_text)
    company_names = [ent.text for ent in doc.ents if ent.label_ == 'ORG']  # 'ORG'は組織名（会社名）を示す
    return company_names

# Google検索で会社設立年を取得する関数
def get_company_foundation_year(company_name):
    # Googleで検索
    query = f"{company_name} 会社設立年"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    search_url = f"https://www.google.com/search?q={query}"
    response = requests.get(search_url, headers=headers)

    # BeautifulSoupでHTMLをパース
    soup = BeautifulSoup(response.text, 'html.parser')
    year_info = soup.find('div', {'class': 'BNeawe iBp4i AP7Wnd'})  # Google検索結果内の設立年情報を取得
    if year_info:
        return year_info.get_text()
    return "不明"

# 設立年数が10年以内でスタートアップかどうかを判定
from datetime import datetime
def is_startup(foundation_year):
    current_year = datetime.now().year
    try:
        foundation_year = int(foundation_year)
        if current_year - foundation_year <= 10:
            return True
    except ValueError:
        pass  # 年が不明な場合はFalseにする
    return False

# RSSフィードから記事情報を取得
def fetch_rss_articles(rss_url):
    feed = feedparser.parse(rss_url)
    articles = []
    for entry in feed.entries:
        article_url = entry.link
        article_title = entry.title
        article_summary = entry.summary
        articles.append({"url": article_url, "title": article_title, "summary": article_summary})
    return articles

# メインの処理
def main():
    # 収集する記事のRSSフィードリスト
    rss_urls = [
        "https://prtimes.jp/main/html/rd/p/0000000000000.rss",
        "https://techblitz.com/feed/",
        "https://kepple.co.jp/feed/",
    ]
    
    # RSSフィードから記事情報を取得
    articles = []
    for rss_url in rss_urls:
        articles.extend(fetch_rss_articles(rss_url))

    # 各記事を処理
    for article in articles:
        url = article["url"]
        title = article["title"]
        summary = article["summary"]
        try:
            # 記事の本文を取得
            article_text = fetch_article_text(url)
            
            # 会社名を抽出
            company_names = extract_company_name(article_text)

            for company_name in company_names:
                # Google検索で設立年を取得
                foundation_year = get_company_foundation_year(company_name)
                
                # スタートアップ判定
                startup_status = is_startup(foundation_year)

                # メッセージ作成
                message = f"New article fetched: {url}\nTitle: {title}\n\n{summary}\n"
                message += f"Company: {company_name}\n"
                message += f"Startup: {'Yes' if startup_status else 'No'}\n"
                message += f"Foundation Year: {foundation_year}\n"
                # 社内データベース検索URL
                message += f"Company Database URL: http://compass/compass/index.cfm#/search/company?text={company_name}&sortKey=note&sortOrder=-1"

                # Slackに送信
                send_slack_message(message)

            print(f"Successfully sent to Slack: {url}")
            time.sleep(5)  # Slack APIに対するリクエスト間隔
        except Exception as e:
            print(f"Failed to fetch article from {url}: {e}")
            send_slack_message(f"Failed to fetch article from {url}: {str(e)}")

if __name__ == "__main__":
    main()
