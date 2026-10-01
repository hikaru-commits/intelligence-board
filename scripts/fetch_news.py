from __future__ import annotations
import json, re, time, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
OUT = ROOT/"data/news.json"
UA = "PersonalIntelligenceBoard/0.1 (+GitHub Actions)"
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language":"ja,en;q=0.8"})

def clean_html(s:str) -> str:
    soup = BeautifulSoup(s or "", "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()

def summary_from_entry(e) -> str:
    raw = e.get("summary") or e.get("description") or ""
    text = clean_html(raw)
    text = re.sub(r"^.*? - ", "", text, count=1) if len(text)>220 else text
    return text[:360]

def published(e):
    for k in ("published","updated","created"):
        if e.get(k):
            try:
                return dtparser.parse(e[k]).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def resolve_google_news_url(url:str) -> str:
    # Google News links are kept as-is for reliability.
    return url

def og_image(url:str) -> str|None:
    try:
        r = session.get(url, timeout=5, allow_redirects=True)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type",""):
            return None
        soup = BeautifulSoup(r.text[:900000], "html.parser")
        for sel, attr in [
            ('meta[property="og:image"]',"content"),
            ('meta[name="twitter:image"]',"content"),
            ('meta[property="twitter:image"]',"content"),
        ]:
            n = soup.select_one(sel)
            if n and n.get(attr):
                return n.get(attr)
    except Exception:
        return None
    return None

def domain_of(url):
    try: return urlparse(url).netloc.lower().replace("www.","")
    except Exception: return ""

def score_item(item, category_priority):
    age_hours = max(0,(datetime.now(timezone.utc)-dtparser.parse(item["published_at"])).total_seconds()/3600)
    freshness = max(0, 30 - age_hours)
    score = category_priority*20 + freshness
    d = domain_of(item["url"])
    if any(d.endswith(x) for x in CFG.get("domain_boost",[])):
        score += 22
    title = item["title"].lower()
    hot = ["breaking","new regulation","amendment","adopted","enters into force","release","launch","新規","改正","発効"]
    if any(k in title for k in hot): score += 8
    return round(score,2)

def google_rss(query, lang="en-US", gl="US", ceid="US:en"):
    u = f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={gl}&ceid={quote(ceid)}"
    return feedparser.parse(u)

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=CFG.get("days_back",7))
    items = []
    seen = set()
    categories = CFG["categories"]
    for cat in categories:
        for q in cat["queries"]:
            feeds = [
                google_rss(q, "en-US","US","US:en"),
                google_rss(q, "ja","JP","JP:ja"),
            ]
            for feed in feeds:
                for e in feed.entries[:20]:
                    dt = published(e)
                    if dt < cutoff: continue
                    title = clean_html(e.get("title",""))
                    url = resolve_google_news_url(e.get("link",""))
                    if not title or not url: continue
                    key = hashlib.sha1(re.sub(r"\W+","",title.lower()).encode()).hexdigest()[:20]
                    if key in seen: continue
                    seen.add(key)
                    source = ""
                    if e.get("source") and isinstance(e.source, dict):
                        source = e.source.get("title","")
                    if not source:
                        source = domain_of(url) or "Google News"
                    item = {
                        "id": key,
                        "category": cat["name"],
                        "priority": cat.get("priority",3),
                        "title": title,
                        "summary": summary_from_entry(e) or "記事を開いて詳細を確認してください。",
                        "source": source,
                        "published_at": dt.isoformat(),
                        "url": url,
                        "image": None,
                    }
                    item["score"] = score_item(item, item["priority"])
                    items.append(item)

    # newest/high-score first; image extraction only for top items to keep Actions fast
    items.sort(key=lambda x:(x["score"],x["published_at"]), reverse=True)
    for item in items[:24]:
        img = og_image(item["url"])
        if img: item["image"] = img
        time.sleep(0.08)

    items = items[:CFG.get("max_items",120)]
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": sum(len(c["queries"]) for c in categories)*2,
        "items": items
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(items)} items -> {OUT}")

if __name__ == "__main__":
    main()
