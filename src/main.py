import os, json, hashlib
import yaml
import feedparser
import requests
from newspaper import Article
from openai import OpenAI
from playwright.sync_api import sync_playwright
from utils import make_compass_url, normalize_company_for_search

TAXONOMY = [
  "通信・ネットワーキング",
  "コンピュータ",
  "半導体/その他電子部品・製品",
  "バイオテクノロジー",
  "医療・ヘルスケア",
  "産業・エネルギー",
  "環境",
  "消費者向けサービス・販売",
  "金融・保険・不動産",
  "ビジネスサービス",
]

SLACK_WEBHOOK = os.environ["SLACK_WEBHOOK_URL"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

STATE_FILE = "state_seen.json"

def load_seen():
    if os.path.exists(STATE_FILE):
        return set(json.load(open(STATE_FILE, "r", encoding="utf-8")))
    return set()

def save_seen(seen):
    json.dump(sorted(list(seen)), open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def fetch_article_text(url: str) -> str:
    a = Article(url)
    a.download()
    a.parse()
    return (a.text or "")[:4000]

def analyze_with_llm(title: str, text: str) -> dict:
    taxonomy_str = "\n".join([f"- {x}" for x in TAXONOMY])
    prompt = f"""
あなたはスタートアップのソーシング担当です。次のタクソノミのいずれか1つに必ず分類してください（新カテゴリ作成禁止）。

【産業分類タクソノミ】
{taxonomy_str}

【出力JSON仕様】（このキー以外は出力しない）
{{
  "company": "会社名（記事中の表記）",
  "company_search": "法人格除去した検索用社名（株式会社等を除去）",
  "is_japan_related": true/false,
  "industry": "上のタクソノミから1つ",
  "confidence": 0.0-1.0,
  "evidence": ["分類根拠キーワードを3個まで"],
  "summary_50": "50字以内の要約"
}}

【記事タイトル】
{title}

【記事本文】
{text}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2,
    )
    content = resp.choices[0].message.content.strip()
    return json.loads(content)

def send_slack(res: dict, article_url: str, source_name: str, article_title: str):
    compass_url = make_compass_url(res["company"])
    msg = (
        f"🚀 *New Startup*（{source_name}）\n"
        f"*会社名*: {res['company']}（検索: {normalize_company_for_search(res['company'])}）\n"
        f"*産業分類*: {res['industry']}（確度 {res['confidence']:.2f}）\n"
        f"*根拠*: {', '.join(res.get('evidence', []))}\n"
        f"*要約*: {res['summary_50']}\n"
        f"<{article_url}|記事を見る>  |  <{compass_url}|Compassで検索>\n"
        f"_Title: {article_title}_"
    )
    requests.post(SLACK_WEBHOOK, json={"text": msg}, timeout=30)

def collect_from_rss(src: dict):
    d = feedparser.parse(src["feed_url"])
    out = []
    for e in d.entries[: src.get("max_items", 20)]:
        out.append({"title": e.title, "url": e.link})
    return out

def collect_from_playwright(src: dict):
    # ここは「ログインして一覧ページからリンクを抜く」最小例
    out = []
    user = os.environ.get(src["username_secret"], "")
    pwd  = os.environ.get(src["password_secret"], "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(src["login_url"], wait_until="domcontentloaded")

        sel = src["selectors"]
        page.fill(sel["username"], user)
        page.fill(sel["password"], pwd)
        page.click(sel["submit"])
        page.wait_for_load_state("networkidle")

        page.goto(src["start_url"], wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        links = page.query_selector_all(sel["article_links"])
        for a in links[: src.get("max_items", 20)]:
            href = a.get_attribute("href")
            title = (a.inner_text() or "").strip()
            if href:
                if href.startswith("/"):
                    # 同一ドメイン想定
                    href = page.url.split("/", 3)[0] + "//" + page.url.split("/", 3)[2] + href
                out.append({"title": title or "No title", "url": href})

        browser.close()

    return out

def main():
    cfg = yaml.safe_load(open("config/sources.yml", "r", encoding="utf-8"))
    seen = load_seen()

    for src in cfg["sources"]:
        if src["type"] == "rss":
            items = collect_from_rss(src)
        elif src["type"] == "playwright":
            items = collect_from_playwright(src)
        else:
            continue

        for it in items:
            key = hashlib.sha256(it["url"].encode("utf-8")).hexdigest()
            if key in seen:
                continue

            try:
                text = fetch_article_text(it["url"])
                if not text.strip():
                    seen.add(key)
                    continue

                res = analyze_with_llm(it["title"], text)

                # 会社名が空/不明ならスキップ
                if not res.get("company"):
                    seen.add(key); continue

                # 日本関連のみ通知（必要なら条件を変更）
                if res.get("is_japan_related") is True:
                    send_slack(res, it["url"], src["name"], it["title"])

                seen.add(key)

            except Exception as ex:
                # 失敗時もURLはseenに入れない（後で再試行できる）
                print(f"Error: {it['url']} -> {ex}")

    save_seen(seen)

if __name__ == "__main__":
    main()
