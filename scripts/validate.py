from pathlib import Path
import json,sys

ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/"data/news.json").read_text(encoding="utf-8"))
items=p.get("items",[])
errors=[]
if not items:errors.append("news.json has no items")
ids=set()
for i,x in enumerate(items):
    for k in ("id","category","title","source","published_at","url","score"):
        if x.get(k) in (None,""):errors.append(f"item[{i}] missing {k}")
    if x.get("id") in ids:errors.append(f"duplicate id {x.get('id')}")
    ids.add(x.get("id"))
    if x.get("title_ja") and not x.get("summary_ja"):errors.append(f"{x.get('id')} title_ja without summary_ja")
    if x.get("content_text") and len(x.get("content_text","")) < 200:errors.append(f"{x.get('id')} suspiciously short content_text")
if errors:
    print("\n".join(errors[:40]));sys.exit(1)
print(f"OK: {len(items)} items, {sum(1 for x in items if x.get('title_ja'))} enriched")
