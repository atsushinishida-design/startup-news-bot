import re
from urllib.parse import quote

CORP_PATTERNS = [
    r"株式会社", r"（株）", r"\(株\)", r"㈱",
    r"有限会社", r"（有）", r"\(有\)", r"㈲",
    r"合同会社", r"（同）", r"\(同\)",
    r"合資会社", r"合名会社",
    r"一般社団法人", r"一般財団法人",
    r"公益社団法人", r"公益財団法人",
    r"学校法人", r"医療法人", r"社会福祉法人",
    r"特定非営利活動法人", r"NPO法人",
]
CORP_PATTERNS_EN = [
    r"\bInc\.?\b", r"\bIncorporated\b",
    r"\bLtd\.?\b", r"\bLimited\b",
    r"\bLLC\b", r"\bCo\.?\b", r"\bCorp\.?\b",
]

CORP_RE = re.compile(rf"^(?:{'|'.join(CORP_PATTERNS)})\s*|\s*(?:{'|'.join(CORP_PATTERNS)})$")
CORP_EN_RE = re.compile(rf"^(?:{'|'.join(CORP_PATTERNS_EN)})\s*|\s*(?:{'|'.join(CORP_PATTERNS_EN)})$", re.IGNORECASE)

def normalize_company_for_search(name: str) -> str:
    if not name:
        return name
    s = name.strip()
    prev = None
    while prev != s:
        prev = s
        s = CORP_RE.sub("", s).strip()
        s = CORP_EN_RE.sub("", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def make_compass_url(company_raw: str) -> str:
    company_q = normalize_company_for_search(company_raw)
    base = "http://compass/compass/index.cfm#/search/company"
    return f"{base}?text={quote(company_q)}&sortKey=note&sortOrder=-1"
