from __future__ import annotations
import json, re, time, hashlib
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
OUT = ROOT/"data/news.json"
UA = "PersonalIntelligenceBoard/0.2 (+GitHub Actions)"
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language":"ja,en;q=0.8"})

GOOGLE_HOSTS = ("news.google.com","google.com","www.google.com","gstatic.com","googleusercontent.com")

def clean_html(s:str) -> str:
    soup = BeautifulSoup(s or "", "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()

def published(e):
    for k in ("published","updated","created"):
        if e.get(k):
            try:
                return dtparser.parse(e[k]).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def domain_of(url):
    try:
        return urlparse(url).netloc.lower().replace("www.","")
    except Exception:
        return ""

def is_google_url(url:str) -> bool:
    d = domain_of(url)
    return any(d == h or d.endswith("." + h) for h in GOOGLE_HOSTS)

def extract_source_url(e) -> str:
    raw = e.get("summary") or e.get("description") or ""
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href","").strip()
            if href.startswith("http") and not is_google_url(href):
                return href
    except Exception:
        pass
    return e.get("link","")

def media_image(e) -> str|None:
    for key in ("media_content","media_thumbnail"):
        vals = e.get(key) or []
        for v in vals:
            if isinstance(v, dict):
                u = (v.get("url") or "").strip()
                if u and not is_google_url(u):
                    return u
    raw = e.get("summary") or e.get("description") or ""
    try:
        soup = BeautifulSoup(raw, "html.parser")
        img = soup.find("img", src=True)
        if img:
            u = img.get("src","").strip()
            if u and u.startswith("http") and not is_google_url(u):
                return u
    except Exception:
        pass
    return None

def summary_from_entry(e) -> str:
    raw = e.get("summary") or e.get("description") or ""
    text = clean_html(raw)
    text = re.sub(r"\s+[\-–—]\s+[^\-–—]{2,80}$", "", text).strip()
    if len(text) > 420:
        text = text[:417].rstrip() + "..."
    return text

def og_image(url:str) -> str|None:
    if not url or is_google_url(url):
        return None
    try:
        r = session.get(url, timeout=7, allow_redirects=True)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type",""):
            return None
        final_url = r.url
        soup = BeautifulSoup(r.text[:1000000], "html.parser")
        for sel, attr in [
            ('meta[property="og:image"]',"content"),
            ('meta[name="twitter:image"]',"content"),
            ('meta[property="twitter:image"]',"content"),
        ]:
            n = soup.select_one(sel)
            if n and n.get(attr):
                u = urljoin(final_url, n.get(attr).strip())
                if u.startswith("http") and not is_google_url(u):
                    return u
    except Exception:
        return None
    return None

def normalize_title(title:str) -> str:
    s = clean_html(title).lower()
    s = re.sub(r"\s+[\-–—|:]\s+[^\-–—|:]{2,80}$", "", s)
    s = re.sub(r"[^0-9a-zぁ-んァ-ン一-龯]+", "", s)
    return s

def title_similarity(a:str, b:str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return min(len(na),len(nb)) / max(len(na),len(nb))
    return SequenceMatcher(None, na, nb).ratio()

def score_item(item, category_priority, official=False):
    age_hours = max(0,(datetime.now(timezone.utc)-dtparser.parse(item["published_at"])).total_seconds()/3600)
    freshness = max(0, 36-age_hours)
    score = category_priority*20 + freshness
    d = domain_of(item["url"])
    if official:
        score += 35
    elif any(d.endswith(x) for x in CFG.get("domain_boost",[])):
        score += 22
    title = item["title"].lower()
    hot = ["breaking","regulation","amendment","adopted","enters into force","effective",
           "release","launch","guideline","circular","update","新規","改正","発効","施行","採択","ガイドライン","通達"]
    if any(k in title for k in hot):
        score += 8
    return round(score,2)

def google_rss(query, lang="en-US", gl="US", ceid="US:en"):
    u = f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={gl}&ceid={quote(ceid)}"
    return feedparser.parse(u)

def add_entry(items, seen_exact, e, cat, official=False):
    dt = published(e)
    cutoff = datetime.now(timezone.utc)-timedelta(days=CFG.get("days_back",7))
    if dt < cutoff:
        return
    title = clean_html(e.get("title",""))
    url = extract_source_url(e)
    if not title or not url:
        return
    exact_key = hashlib.sha1(normalize_title(title).encode()).hexdigest()[:20]
    if exact_key in seen_exact:
        return
    seen_exact.add(exact_key)

    source = ""
    if e.get("source") and isinstance(e.source, dict):
        source = e.source.get("title","")
    if not source:
        source = domain_of(url) or "Google News"

    item = {
        "id": exact_key,
        "category": cat["name"],
        "priority": cat.get("priority",3),
        "title": title,
        "summary": summary_from_entry(e) or "記事を開いて詳細を確認してください。",
        "source": source,
        "published_at": dt.isoformat(),
        "url": url,
        "image": media_image(e),
        "official": bool(official),
        "cluster_count": 1,
        "related_sources": [source] if source else [],
    }
    item["score"] = score_item(item, item["priority"], official=official)
    items.append(item)

def cluster_similar(items):
    ordered = sorted(items, key=lambda x:(x["score"],x["published_at"]), reverse=True)
    clusters = []
    for item in ordered:
        match = None
        for rep in clusters:
            if item["category"] != rep["category"]:
                continue
            if title_similarity(item["title"], rep["title"]) >= 0.84:
                match = rep
                break
        if match is None:
            clusters.append(item)
            continue
        match["cluster_count"] = match.get("cluster_count",1)+1
        srcs = match.setdefault("related_sources",[])
        if item.get("source") and item["source"] not in srcs:
            srcs.append(item["source"])
        if not match.get("image") and item.get("image"):
            match["image"] = item["image"]
        if is_google_url(match.get("url","")) and not is_google_url(item.get("url","")):
            match["url"] = item["url"]
            match["source"] = item["source"]
        if len(item.get("summary","")) > len(match.get("summary","")):
            match["summary"] = item["summary"]
        match["score"] = max(match["score"],item["score"]) + min(6,match["cluster_count"]-1)
    return clusters

def main():
    items, seen_exact = [], set()
    categories = CFG["categories"]

    for src_cfg in CFG.get("official_sources",[]):
        cat = next((c for c in categories if c["name"] == src_cfg["category"]), None)
        if not cat:
            continue
        for q in src_cfg.get("queries",[]):
            query = f"site:{src_cfg['domain']} {q}"
            for feed in (google_rss(query,"en-US","US","US:en"), google_rss(query,"ja","JP","JP:ja")):
                for e in feed.entries[:12]:
                    add_entry(items,seen_exact,e,cat,official=True)

    for cat in categories:
        for q in cat["queries"]:
            for feed in (google_rss(q,"en-US","US","US:en"), google_rss(q,"ja","JP","JP:ja")):
                for e in feed.entries[:20]:
                    add_entry(items,seen_exact,e,cat,official=False)

    items = cluster_similar(items)
    items.sort(key=lambda x:(x["score"],x["published_at"]), reverse=True)

    for item in items[:32]:
        if not item.get("image"):
            img = og_image(item.get("url",""))
            if img:
                item["image"] = img
        time.sleep(0.05)

    items = items[:CFG.get("max_items",120)]
    if not items and OUT.exists():
        print("0 items fetched; keeping existing data/news.json")
        return

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(CFG.get("official_sources",[])) + sum(len(c["queries"]) for c in categories)*2,
        "version":"0.2",
        "items":items
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"wrote {len(items)} clustered items -> {OUT}")

if __name__ == "__main__":
    main()
