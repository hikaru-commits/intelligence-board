from pathlib import Path
import json,sys,re
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/"data/news.json").read_text(encoding="utf-8"))
items=p.get("items",[])
err=[];warn=[];ids=set()

def dom(u):
    try:return urlparse(u).netloc.lower().removeprefix("www.")
    except Exception:return ""

for i,x in enumerate(items):
    for k in ("id","category","title","source","published_at","url","score"):
        if x.get(k) in (None,""):err.append(f"{i}: missing {k}")
    if x.get("id") in ids:err.append(f"duplicate {x.get('id')}")
    ids.add(x.get("id"))

    # Full text must stay on the expected publisher domain.
    if x.get("content_text") and x.get("expected_domain"):
        d=dom(x.get("url",""));e=x["expected_domain"]
        if not (d==e or d.endswith("."+e)):err.append(f"{x['id']}: fulltext domain mismatch {d} != {e}")

    if x.get("content_status")=="headline" and x.get("key_points"):err.append(f"{x['id']}: headline-only has key points")
    if x.get("summary_ja") and x.get("title_ja"):
        a=re.sub(r"\W+","",x["summary_ja"].lower());b=re.sub(r"\W+","",x["title_ja"].lower())
        if a and b and (a==b or (len(a)>20 and a in b)):warn.append(f"{x['id']}: summary resembles title")

if not items:err.append("no items")
if err:
    print("\n".join(err[:60]));sys.exit(1)
print(json.dumps({
  "items":len(items),
  "fulltext":sum(bool(x.get("content_text")) for x in items),
  "official":sum(bool(x.get("official")) for x in items),
  "clusters":sum(x.get("cluster_count",1)>1 for x in items),
  "warnings":len(warn)
},ensure_ascii=False))
