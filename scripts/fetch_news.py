from __future__ import annotations
import json, re, time, hashlib, os, math
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from trafilatura import extract as trafilatura_extract

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
OUT = ROOT/"data/news.json"
UA = "SignalDeck/2.0.2-free (+GitHub Actions)"
session = requests.Session()
session.headers.update({"User-Agent":UA,"Accept-Language":"ja,en;q=0.8"})
DECODE_STATS={"ok":0,"fail":0}

try:
    from googlenewsdecoder import new_decoderv1
except Exception:
    new_decoderv1 = None

def resolve_google_news_url(url:str) -> str:
    if not url or not is_google_url(url) or new_decoderv1 is None:
        return url
    try:
        result = new_decoderv1(url, interval=0)
        if isinstance(result, dict) and (result.get("success") or result.get("status")) and result.get("decoded_url"):
            DECODE_STATS["ok"]+=1
            return result["decoded_url"]
    except Exception as e:
        print("google decode failed", str(e)[:100])
    DECODE_STATS["fail"]+=1
    return url

GOOGLE_HOSTS=("news.google.com","google.com","www.google.com","gstatic.com","googleusercontent.com")
PERSIST_FIELDS=(
    "title_ja","summary_ja","key_points","why_it_matters","signal",
    "enriched_at","free_enriched_at","enrichment_model","content_text","content_chars",
    "content_extraction","embedding"
)

def clean_html(s:str)->str:
    return re.sub(r"\s+"," ",BeautifulSoup(s or "","html.parser").get_text(" ",strip=True)).strip()

def published(e):
    for k in ("published","updated","created"):
        if e.get(k):
            try:return dtparser.parse(e[k]).astimezone(timezone.utc)
            except Exception:pass
    return datetime.now(timezone.utc)

def domain_of(url):
    try:return urlparse(url).netloc.lower().replace("www.","")
    except Exception:return ""

def is_google_url(url):
    d=domain_of(url)
    return any(d==h or d.endswith("."+h) for h in GOOGLE_HOSTS)

def normalize_title(title):
    s=clean_html(title).lower()
    s=re.sub(r"\s+[\-–—|:]\s+[^\-–—|:]{2,80}$","",s)
    s=re.sub(r"[^0-9a-zぁ-んァ-ン一-龯]+","",s)
    return s

def title_similarity(a,b):
    na,nb=normalize_title(a),normalize_title(b)
    if not na or not nb:return 0
    if na in nb or nb in na:return min(len(na),len(nb))/max(len(na),len(nb))
    return SequenceMatcher(None,na,nb).ratio()

def cosine(a,b):
    if not a or not b or len(a)!=len(b):return 0.0
    return sum(x*y for x,y in zip(a,b))

def extract_source_url(e):
    raw=e.get("summary") or e.get("description") or ""
    try:
        soup=BeautifulSoup(raw,"html.parser")
        for a in soup.find_all("a",href=True):
            href=a.get("href","").strip()
            if href.startswith("http") and not is_google_url(href):return href
    except Exception:pass
    return e.get("link","")

def entry_image(e):
    for key in ("media_content","media_thumbnail"):
        for v in e.get(key) or []:
            if isinstance(v,dict):
                u=(v.get("url") or "").strip()
                if u.startswith("http") and not is_google_url(u):return u
    return None

def summary_from_entry(e):
    text=clean_html(e.get("summary") or e.get("description") or "")
    text=re.sub(r"\s+[\-–—]\s+[^\-–—]{2,80}$","",text).strip()
    return text[:447].rstrip()+"..." if len(text)>450 else text

def og_image(url):
    if not url or is_google_url(url):return None
    try:
        r=session.get(url,timeout=7,allow_redirects=True)
        if r.status_code>=400 or "text/html" not in r.headers.get("content-type",""):return None
        soup=BeautifulSoup(r.text[:1000000],"html.parser")
        for sel in ('meta[property="og:image"]','meta[name="twitter:image"]','meta[property="twitter:image"]'):
            n=soup.select_one(sel)
            if n and n.get("content"):
                u=urljoin(r.url,n["content"].strip())
                if u.startswith("http") and not is_google_url(u):return u
    except Exception:pass
    return None

def extract_article_text(url):
    ecfg=CFG.get("content_extraction",{})
    if not ecfg.get("enabled",True) or not url or is_google_url(url):return None
    try:
        r=session.get(url,timeout=int(ecfg.get("timeout_seconds",9)),allow_redirects=True)
        if r.status_code>=400 or "text/html" not in r.headers.get("content-type",""):return None
        text=trafilatura_extract(
            r.text,
            url=r.url,
            include_comments=False,
            include_tables=False,
            favor_precision=True
        )
        text=re.sub(r"\s+"," ",text or "").strip()
        if len(text)<int(ecfg.get("min_extracted_chars",280)):return None
        return text[:int(ecfg.get("max_chars_per_article",7000))]
    except Exception as e:
        print("extract failed",url,str(e)[:120]);return None

def google_rss(query,lang="en-US",gl="US",ceid="US:en"):
    u=f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={gl}&ceid={quote(ceid)}"
    return feedparser.parse(u)

def score_item(item,priority,official=False):
    age=max(0,(datetime.now(timezone.utc)-dtparser.parse(item["published_at"])).total_seconds()/3600)
    freshness=max(0,40-age)
    score=priority*20+freshness
    if official:score+=35
    elif any(domain_of(item["url"]).endswith(x) for x in CFG.get("domain_boost",[])):score+=20
    hot=("regulation","amendment","adopted","enters into force","release","launch","guideline","circular","update",
         "改正","発効","施行","採択","ガイドライン","通達","新モデル")
    if any(k in item["title"].lower() for k in hot):score+=8
    return round(score,2)

def add_entry(items,seen,e,cat,official=False,source_override=None):
    dt=published(e)
    if dt < datetime.now(timezone.utc)-timedelta(days=CFG.get("days_back",7)):return
    title=clean_html(e.get("title",""))
    url=resolve_google_news_url(extract_source_url(e))
    if not title or not url:return
    key=hashlib.sha1(normalize_title(title).encode()).hexdigest()[:20]
    if key in seen:return
    seen.add(key)
    source=source_override or ""
    if not source and e.get("source") and isinstance(e.source,dict):source=e.source.get("title","")
    if not source:source=domain_of(url) or "Feed"
    item={
        "id":key,"category":cat["name"],"priority":cat.get("priority",3),
        "title":title,"summary":summary_from_entry(e) or "記事を開いて詳細を確認してください。",
        "source":source,"source_type":"official" if official else "news",
        "published_at":dt.isoformat(),"url":url,"image":entry_image(e),
        "official":bool(official),"cluster_count":1,"related_sources":[source] if source else []
    }
    item["score"]=score_item(item,item["priority"],official)
    items.append(item)

def fetch_rsshub(items,seen):
    base=os.getenv("RSSHUB_BASE_URL","").strip().rstrip("/")
    routes=CFG.get("rsshub",{}).get("routes",[])
    if not base or not routes:return
    cats={c["name"]:c for c in CFG["categories"]}
    for spec in routes:
        route=spec.get("route","").strip()
        cat=cats.get(spec.get("category"))
        if not route or not cat:continue
        try:
            feed=feedparser.parse(base + "/" + route.lstrip("/"))
            for e in feed.entries[:30]:
                add_entry(items,seen,e,cat,bool(spec.get("official",False)),spec.get("source"))
        except Exception as e:print("rsshub error",route,e)

def cluster_lexical(items):
    ordered=sorted(items,key=lambda x:(x["score"],x["published_at"]),reverse=True)
    out=[]
    for item in ordered:
        match=None
        for rep in out:
            if item["category"]!=rep["category"]:continue
            if title_similarity(item["title"],rep["title"])>=0.84:
                match=rep;break
        if not match:
            out.append(item);continue
        merge_into(match,item)
    return out

def merge_into(match,item):
    match["cluster_count"]=match.get("cluster_count",1)+1
    if item.get("source") and item["source"] not in match["related_sources"]:match["related_sources"].append(item["source"])
    if not match.get("image") and item.get("image"):match["image"]=item["image"]
    if is_google_url(match.get("url","")) and not is_google_url(item.get("url","")):
        match["url"],match["source"]=item["url"],item["source"]
    if len(item.get("summary",""))>len(match.get("summary","")):match["summary"]=item["summary"]
    match["score"]=max(match["score"],item["score"])+min(6,match["cluster_count"]-1)

def x_engagement_score(m):
    raw=int(m.get("like_count",0) or 0)+2*int(m.get("retweet_count",0) or 0)+int(m.get("reply_count",0) or 0)+3*int(m.get("quote_count",0) or 0)
    return int(round(math.log2(raw+1)*10)) if raw else 0

def fetch_x_posts():
    token=os.getenv("X_BEARER_TOKEN","").strip()
    xcfg=CFG.get("x_watch",{})
    if not token:return []
    headers={"Authorization":f"Bearer {token}","User-Agent":UA}
    items=[];seen=set()
    for query in xcfg.get("queries",[]):
        try:
            r=requests.get("https://api.x.com/2/tweets/search/recent",headers=headers,params={
                "query":query,"max_results":50,
                "tweet.fields":"created_at,public_metrics,lang,author_id",
                "expansions":"author_id","user.fields":"username,name,verified"
            },timeout=12)
            if r.status_code>=400:
                print("X skipped",r.status_code);continue
            p=r.json();users={u["id"]:u for u in p.get("includes",{}).get("users",[])}
            for post in p.get("data",[]):
                pid=post.get("id");txt=clean_html(post.get("text",""))
                if not pid or not txt or pid in seen:continue
                seen.add(pid)
                metrics=post.get("public_metrics",{}) or {}
                engagement=x_engagement_score(metrics)
                if engagement<int(xcfg.get("minimum_engagement_score",0)):continue
                user=users.get(post.get("author_id"),{});username=user.get("username","")
                src=f"@{username}" if username else "X"
                items.append({
                    "id":f"x-{pid}","category":"AI・DX","priority":4,
                    "title":txt[:220],"summary":f"Xで注目されている投稿。いいね {metrics.get('like_count',0)} / リポスト {metrics.get('retweet_count',0)} / 返信 {metrics.get('reply_count',0)}",
                    "source":src,"source_type":"x","published_at":post.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    "url":f"https://x.com/{username}/status/{pid}" if username else f"https://x.com/i/web/status/{pid}",
                    "image":None,"official":False,"cluster_count":1,"related_sources":[src],
                    "engagement":metrics,"engagement_score":engagement,"score":95+engagement
                })
        except Exception as e:print("X error",e)
    items.sort(key=lambda x:(x["engagement_score"],x["published_at"]),reverse=True)
    return items[:int(xcfg.get("max_items",18))]

def previous_data():
    url=CFG.get("published_data_url")
    if not url:return {}
    try:
        r=session.get(url,timeout=8)
        if r.ok:
            p=r.json()
            return {x["id"]:x for x in p.get("items",[]) if x.get("id")}
    except Exception:pass
    return {}

def char_ngrams(text,n=3):
    s=re.sub(r"\s+"," ",(text or "").lower())
    s=re.sub(r"[^\w一-龯ぁ-んァ-ン ]+","",s)
    s=s.replace(" ","")
    if len(s)<n:return set()
    return {s[i:i+n] for i in range(len(s)-n+1)}

def free_semantic_similarity(a,b):
    ta=char_ngrams((a.get("title_ja") or a.get("title") or "")+" "+(a.get("summary_ja") or a.get("summary") or ""))
    tb=char_ngrams((b.get("title_ja") or b.get("title") or "")+" "+(b.get("summary_ja") or b.get("summary") or ""))
    if not ta or not tb:return 0.0
    return len(ta & tb) / len(ta | tb)

def semantic_merge(items):
    scfg=CFG.get("semantic_clustering",{})
    threshold=float(scfg.get("similarity_threshold",0.80))
    out=[]
    for item in sorted(items,key=lambda x:(x["score"],x["published_at"]),reverse=True):
        match=None
        for rep in out:
            if item["category"]!=rep["category"]:continue
            # combine lexical title and char-ngram semantic-ish similarity
            sim=max(title_similarity(item["title"],rep["title"]), free_semantic_similarity(item,rep))
            if sim>=threshold:
                match=rep;break
        if match:merge_into(match,item)
        else:out.append(item)
    return out

def main():
    categories=CFG["categories"];items=[];seen=set()
    for src in CFG.get("official_sources",[]):
        cat=next((c for c in categories if c["name"]==src["category"]),None)
        if not cat:continue
        for q in src.get("queries",[]):
            query=f"site:{src['domain']} {q}"
            for feed in (google_rss(query,"en-US","US","US:en"),google_rss(query,"ja","JP","JP:ja")):
                for e in feed.entries[:12]:add_entry(items,seen,e,cat,True)

    for cat in categories:
        for q in cat["queries"]:
            for feed in (google_rss(q,"en-US","US","US:en"),google_rss(q,"ja","JP","JP:ja")):
                for e in feed.entries[:20]:add_entry(items,seen,e,cat,False)

    fetch_rsshub(items,seen)
    items=cluster_lexical(items)
    items.sort(key=lambda x:(x["score"],x["published_at"]),reverse=True)

    prior=previous_data()
    for item in items:
        old=prior.get(item["id"],{})
        for f in PERSIST_FIELDS:
            if old.get(f) is not None:item[f]=old[f]

    # Extract article bodies only for new/high-value articles; reuse cached extraction thereafter.
    ecfg=CFG.get("content_extraction",{})
    budget=int(ecfg.get("max_new_articles_per_run",18))
    extracted=0
    for item in items:
        if extracted>=budget:break
        if item.get("source_type")=="x" or item.get("content_text"):continue
        text=extract_article_text(item.get("url",""))
        if text:
            item["content_text"]=text
            item["content_chars"]=len(text)
            item["content_extraction"]="trafilatura"
            extracted+=1

    for item in items[:28]:
        if not item.get("image") and item.get("source_type")!="x":
            item["image"]=og_image(item.get("url",""))
        time.sleep(.03)

    items=semantic_merge(items)
    items.sort(key=lambda x:(x["score"],x["published_at"]),reverse=True)
    items=items[:CFG.get("max_items",120)]

    if not items and OUT.exists():
        print("0 items; preserving existing data");return

    payload={
        "updated_at":datetime.now(timezone.utc).isoformat(),
        "source_count":len(CFG.get("official_sources",[]))+sum(len(c["queries"]) for c in categories)*2+len(CFG.get("rsshub",{}).get("routes",[])),
        "version":"2.0.2-free",
        "content_extracted_count":sum(1 for x in items if x.get("content_text")),
        "semantic_clustered":True,
        "items":items
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("wrote",len(items),"items;",payload["content_extracted_count"],"with article text;",f"decoded={DECODE_STATS['ok']}, decode_fail={DECODE_STATS['fail']}")

if __name__=="__main__":main()
