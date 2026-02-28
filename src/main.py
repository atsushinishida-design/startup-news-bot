# 記事URLから本文を取得する関数
def fetch_article_text(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    r = requests.get(url, timeout=30, headers=headers)  # ヘッダーにUser-Agentを追加
    r.raise_for_status()
    html = r.text

    # Documentクラスを使って記事本文を抽出
    doc = Document(html)
    content_html = doc.summary()  # summaryメソッドで本文を抽出
    title = doc.title()  # 記事のタイトルを取得

    soup = BeautifulSoup(content_html, "lxml")
    text = soup.get_text(separator="\n")
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
    
    return title, text[:4000]  # タイトルと本文を返す
