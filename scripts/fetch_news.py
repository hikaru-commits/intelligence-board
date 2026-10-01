from __future__ import annotations
import json, re, hashlib, os, time
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from trafilatura import extract as trafilatura_extract

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
OUT=ROOT/"data/news.json"
UA="SignalDeck/3.0.1-free"
S=requests.Session()
S.headers.update({"User-Agent":UA,"Accept-Language":"ja,en;q=0.8"})
GOOGLE_HOSTS=("news.google.com","google.com","www.google.com","gstatic.com","googleusercontent.com")
STATS={"google_decode_ok":0,"google_decode_fail":0,"resolve_attempted":0,"resolved":0,"extracted":0,"direct_feed":0}

try:
    from googlenewsdecoder import new_decoderv1
except Exception:
    new_decoderv1=None

def clean(s):
    return re.sub(r"\s+"," ",BeautifulSoup(s or "","html.parser").get_text(" ",strip=True)).strip()

def domain(url):
    try:return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:return ""

def is_google(url):
    d=domain(url)
    return any(d==h or d.endswith("."+h) for h in GOOGLE_HOSTS)

def domain_matches(url, expected):
    d=domain(url); e=(expected or "").lower().removeprefix("www.")
    return bool(d and e and (d==e or d.endswith("."+e)))

def dt_of(e):
    for k in ("published","updated","created"):
        if e.get(k):
            try:return dtparser.parse(e[k]).astimezone(timezone.utc)
            except Exception:pass
    return datetime.now(timezone.utc)

def norm_title(s):
    s=clean(s).lower()
    s=re.sub(r"\s+[-–—|]\s+[^-–—|]{2,90}$","",s)
    return re.sub(r"[^0-9a-zぁ-んァ-ン一-龯]+","",s)

def title_similarity(a,b):
    a,b=norm_title(a),norm_title(b)
    if not a or not b:return 0.0
    return SequenceMatcher(None,a,b).ratio()

def publisher_suffix(title, source):
    t=(title or "").strip(); s=(source or "").strip()
    if not s:return t
    for sep in (" - "," | "," – "," — "):
        if sep in t:
            left,right=t.rsplit(sep,1)
            if norm_title(right)==norm_title(s) or norm_title(s) in norm_title(right):
                return left.strip()
    return t

def google_decode(url):
    if not url or not is_google(url) or not new_decoderv1:return url
    try:
        r=new_decoderv1(url,interval=0)
        if isinstance(r,dict) and (r.get("success") or r.get("status")) and r.get("decoded_url"):
            STATS["google_decode_ok"]+=1
            return r["decoded_url"]
    except Exception:
        pass
    STATS["google_decode_fail"]+=1
    return url

def rss_google(query,lang="en-US",gl="US",ceid="US:en"):
    url=f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={gl}&ceid={quote(ceid)}"
    return feedparser.parse(url)

def rss_bing(query):
    try:
        r=S.get("https://www.bing.com/search",params={"q":query,"format":"rss","mkt":"en-US"},timeout=10)
        return feedparser.parse(r.content) if r.ok else None
    except Exception:return None

def entry_source(e):
    src=e.get("source")
    if isinstance(src,dict):
        return clean(src.get("title","")), (src.get("href") or "")
    return "", ""

def entry_image(e):
    for k in ("media_content","media_thumbnail"):
        for v in e.get(k) or []:
            if isinstance(v,dict):
                u=(v.get("url") or "").strip()
                if u.startswith("http") and not is_google(u):return u
    return None

def og_image(url):
    if not url or is_google(url):return None
    try:
        r=S.get(url,timeout=7,allow_redirects=True)
        if not r.ok or "text/html" not in r.headers.get("content-type",""):return None
        soup=BeautifulSoup(r.text[:800000],"html.parser")
        for sel in ('meta[property="og:image"]','meta[name="twitter:image"]'):
            n=soup.select_one(sel)
            if n and n.get("content"):
                u=urljoin(r.url,n["content"].strip())
                if u.startswith("http") and not is_google(u):return u
    except Exception:pass
    return None

def extract_text(url):
    if not url or is_google(url):return None
    c=CFG["content_extraction"]
    try:
        r=S.get(url,timeout=int(c["timeout_seconds"]),allow_redirects=True)
        if not r.ok or "text/html" not in r.headers.get("content-type",""):return None
        text=trafilatura_extract(r.text,url=r.url,include_comments=False,include_tables=False,include_links=False,favor_precision=True)
        text=re.sub(r"\s+"," ",text or "").strip()
        if len(text)<int(c["min_extracted_chars"]):return None
        return text[:int(c["max_chars_per_article"])]
    except Exception:return None

def safe_search_resolve(title, expected_domain):
    """Resolve by title only when the candidate stays on the expected publisher domain."""
    if not title or not expected_domain:return None
    feed=rss_bing(f'site:{expected_domain} "{publisher_suffix(title, "")}"')
    if not feed:return None
    best=None
    for e in feed.entries[:8]:
        u=(e.get("link") or "").strip()
        if not domain_matches(u,expected_domain):continue
        sim=title_similarity(title,clean(e.get("title","")))
        if sim>=0.68 and (best is None or sim>best[0]):best=(sim,u)
    return best[1] if best else None

def resolve_url(raw_url,title,expected_domain):
    STATS["resolve_attempted"]+=1
    candidates=[]
    if raw_url:
        d=google_decode(raw_url) if is_google(raw_url) else raw_url
        if d and not is_google(d):candidates.append(d)
    searched=safe_search_resolve(title,expected_domain)
    if searched and searched not in candidates:candidates.append(searched)

    for u in candidates:
        # Official/source-constrained items must remain on the expected publisher.
        if expected_domain and not domain_matches(u,expected_domain):continue
        text=extract_text(u)
        if text:
            STATS["resolved"]+=1; STATS["extracted"]+=1
            return u,text
    return raw_url,None

def score(item):
    age=max(0,(datetime.now(timezone.utc)-dtparser.parse(item["published_at"])).total_seconds()/3600)
    freshness=max(0,48-age)
    q={"official":28,"news":10,"social":3}.get(item["source_type"],5)
    return round(item["priority"]*20+freshness+q+min(10,(item.get("cluster_count",1)-1)*2),2)

def add(items,seen,e,cat,source_override="",expected_domain="",official_candidate=False,source_type="news"):
    dt=dt_of(e)
    if dt < datetime.now(timezone.utc)-timedelta(days=CFG["days_back"]):return
    title=clean(e.get("title",""))
    if not title:return
    key=hashlib.sha1(norm_title(title).encode()).hexdigest()[:20]
    if key in seen:return
    seen.add(key)

    src_title,src_href=entry_source(e)
    source=source_override or src_title or domain(e.get("link","")) or "Feed"
    expected=expected_domain or domain(src_href)
    raw=(e.get("link") or "").strip()

    # A site-restricted item is "official" only when the feed's source href or direct URL matches.
    official=bool(official_candidate and (
        domain_matches(src_href,expected_domain) or
        (raw and not is_google(raw) and domain_matches(raw,expected_domain))
    ))

    summary=clean(e.get("summary") or e.get("description") or "")
    item={
        "id":key,"category":cat["name"],"priority":cat["priority"],
        "title":publisher_suffix(title,source),"summary":summary,
        "source":source,"source_type":"official" if official else source_type,
        "official":official,"expected_domain":expected,
        "published_at":dt.isoformat(),"url":raw,"image":entry_image(e),
        "cluster_count":1,"related_sources":[source],"related_articles":[]
    }
    item["score"]=score(item)
    items.append(item)

def fetch_direct(items,seen):
    cats={c["name"]:c for c in CFG["categories"]}
    for spec in CFG.get("direct_feeds",[]):
        cat=cats.get(spec["category"])
        if not cat:continue
        feed=feedparser.parse(spec["url"])
        for e in feed.entries[:30]:
            add(items,seen,e,cat,spec["source"],spec["domain"],True,"news")
            if items:
                # direct feeds are trusted direct URLs
                items[-1]["official"]=True
                items[-1]["source_type"]="official"
                items[-1]["expected_domain"]=spec["domain"]
                STATS["direct_feed"]+=1

def fetch_google(items,seen):
    for spec in CFG.get("official_sources",[]):
        cat=next(c for c in CFG["categories"] if c["name"]==spec["category"])
        for q in spec["queries"]:
            for f in (rss_google(f'site:{spec["domain"]} {q}'),rss_google(f'site:{spec["domain"]} {q}',"ja","JP","JP:ja")):
                for e in f.entries[:12]:
                    add(items,seen,e,cat,spec["source"],spec["domain"],True,"news")
    for cat in CFG["categories"]:
        for q in cat["queries"]:
            for f in (rss_google(q),rss_google(q,"ja","JP","JP:ja")):
                for e in f.entries[:18]:
                    add(items,seen,e,cat)

def fetch_social(items,seen):
    if not CFG.get("social_discovery",{}).get("enabled"):return
    cat=next(c for c in CFG["categories"] if c["name"]=="AI・DX")
    count=0
    for q in CFG["social_discovery"]["queries"]:
        f=rss_bing(q)
        if not f:continue
        for e in f.entries[:10]:
            u=(e.get("link") or "")
            if not re.search(r"https?://(www\.)?(x|twitter)\.com/.+/status/\d+",u):continue
            add(items,seen,e,cat,domain(u),domain(u),False,"social")
            count+=1
            if count>=CFG["social_discovery"]["max_items"]:return

def previous():
    try:
        r=S.get(CFG["published_data_url"],timeout=8)
        if r.ok:
            return {x["id"]:x for x in r.json().get("items",[]) if x.get("id")}
    except Exception:pass
    return {}

def main():
    items=[];seen=set()
    fetch_direct(items,seen)
    fetch_google(items,seen)
    fetch_social(items,seen)

    old=previous()
    reusable_meta=("title_ja","summary_ja","key_points","why_it_matters","signal","free_enriched_at","free_enrich_version")
    for x in items:
        o=old.get(x["id"],{})

        # Reuse presentation/enrichment metadata, but NEVER blindly reuse old article bodies.
        for k in reusable_meta:
            if k in o:
                x[k]=o[k]

        old_url=(o.get("url") or "").strip()
        safe_old_content=(
            bool(o.get("content_text")) and
            bool(old_url) and
            not is_google(old_url) and
            (not x.get("expected_domain") or domain_matches(old_url,x["expected_domain"]))
        )
        if safe_old_content:
            x["url"]=old_url
            x["content_text"]=o["content_text"]
            x["content_chars"]=o.get("content_chars",len(o["content_text"]))
            x["content_extraction"]=o.get("content_extraction","trafilatura")
        else:
            x.pop("content_text",None)
            x.pop("content_chars",None)
            x.pop("content_extraction",None)

    budget=CFG["content_extraction"]["max_new_articles_per_run"]
    done=0
    for x in sorted(items,key=lambda z:z["score"],reverse=True):
        if done>=budget:break
        if x.get("content_text"):continue
        # Only try full text when we know the publisher domain.
        if not x.get("expected_domain"):continue
        u,text=resolve_url(x.get("url",""),x["title"],x["expected_domain"])
        if text:
            x["url"]=u;x["content_text"]=text;x["content_chars"]=len(text);x["content_extraction"]="trafilatura";done+=1

    for x in sorted(items,key=lambda z:z["score"],reverse=True)[:24]:
        if not x.get("image") and x.get("url") and not is_google(x["url"]):
            x["image"]=og_image(x["url"])

    items=sorted(items,key=lambda z:(z["score"],z["published_at"]),reverse=True)[:CFG["max_items"]]
    payload={
        "updated_at":datetime.now(timezone.utc).isoformat(),
        "version":"3.0.1-free",
        "source_count":len(CFG.get("direct_feeds",[]))+len(CFG.get("official_sources",[]))+sum(len(c["queries"]) for c in CFG["categories"]),
        "content_extracted_count":sum(bool(x.get("content_text")) for x in items),
        "resolver_stats":STATS,
        "items":items
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"items":len(items),"full_text":payload["content_extracted_count"],**STATS},ensure_ascii=False))

if __name__=="__main__":main()
