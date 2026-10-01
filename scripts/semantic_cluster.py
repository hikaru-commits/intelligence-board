from __future__ import annotations
import json,re
from pathlib import Path
import numpy as np
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
PATH=ROOT/"data/news.json"

def norm(s):
    return re.sub(r"[^0-9a-zぁ-んァ-ン一-龯]+","",(s or "").lower())

def lexical(a,b):
    return SequenceMatcher(None,norm(a),norm(b)).ratio()

def versions(title):
    # Prevent "Gemini 3.8" and "Gemini 4" style stories from being merged.
    return set(re.findall(r"\b\d+(?:\.\d+){0,2}\b",title or ""))

def compatible(a,b):
    va,vb=versions(a.get("title","")),versions(b.get("title",""))
    if va and vb and va.isdisjoint(vb):return False
    return True

def cos(a,b):
    return float(np.dot(a,b)/((np.linalg.norm(a)*np.linalg.norm(b))+1e-12))

def merge(rep,x):
    rep["cluster_count"]=rep.get("cluster_count",1)+1
    if x.get("source") and x["source"] not in rep.setdefault("related_sources",[]):rep["related_sources"].append(x["source"])
    rep.setdefault("related_articles",[]).append({"title":x.get("title"),"source":x.get("source"),"url":x.get("url"),"published_at":x.get("published_at")})
    if not rep.get("image") and x.get("image"):rep["image"]=x["image"]
    rep["score"]=max(rep.get("score",0),x.get("score",0))+min(8,rep["cluster_count"]-1)

def main():
    data=json.loads(PATH.read_text(encoding="utf-8"))
    items=data.get("items",[])
    if not items:return
    cfg=CFG["semantic_clustering"]
    try:
        from fastembed import TextEmbedding
        model=TextEmbedding(model_name=cfg["model"],cache_dir=str(ROOT/".cache/fastembed"),threads=2)
        subset=items[:int(cfg["max_items"])]
        texts=["passage: "+((x.get("title") or "")+"\n"+(x.get("content_text") or x.get("summary") or "")[:1600]) for x in subset]
        vecs=[np.asarray(v,dtype=np.float32) for v in model.embed(texts,batch_size=16)]
    except Exception as e:
        print("FastEmbed fallback:",e)
        subset=items;vecs=[None]*len(items)

    kept=[];kvec=[]
    for x,v in zip(subset,vecs):
        hit=-1;best=0.0
        for i,(rep,rv) in enumerate(zip(kept,kvec)):
            if x.get("category")!=rep.get("category") or not compatible(x,rep):continue
            sim=lexical(x.get("title",""),rep.get("title",""))
            if v is not None and rv is not None:sim=max(sim,cos(v,rv))
            if sim>best:best,hit=sim,i
        threshold=float(cfg["similarity_threshold"])
        if hit>=0 and best>=threshold:merge(kept[hit],x)
        else:kept.append(x);kvec.append(v)

    if len(items)>len(subset):kept.extend(items[len(subset):])
    kept.sort(key=lambda x:(x.get("score",0),x.get("published_at","")),reverse=True)
    data["items"]=kept
    data["semantic_clustered"]=True
    data["semantic_merged_count"]=len(items)-len(kept)
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"clusters {len(items)} -> {len(kept)}")

if __name__=="__main__":main()
