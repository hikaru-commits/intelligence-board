from __future__ import annotations
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
PATH=ROOT/"data/news.json"

def cosine(a,b):
    return float(np.dot(a,b)/((np.linalg.norm(a)*np.linalg.norm(b))+1e-12))

def merge(rep,item):
    rep["cluster_count"]=rep.get("cluster_count",1)+1
    if item.get("source") and item["source"] not in rep.setdefault("related_sources",[]):
        rep["related_sources"].append(item["source"])
    rep.setdefault("related_articles",[]).append({
        "title":item.get("title"),"source":item.get("source"),"url":item.get("url"),
        "published_at":item.get("published_at"),"source_type":item.get("source_type")
    })
    if not rep.get("image") and item.get("image"): rep["image"]=item["image"]
    if len(item.get("summary",""))>len(rep.get("summary","")): rep["summary"]=item["summary"]
    rep["score"]=max(rep.get("score",0),item.get("score",0))+min(8,rep["cluster_count"]-1)

def main():
    data=json.loads(PATH.read_text(encoding="utf-8"))
    items=data.get("items",[])
    scfg=CFG.get("semantic_clustering",{})
    if not items or scfg.get("mode")!="fastembed": return
    try:
        from fastembed import TextEmbedding
        model=TextEmbedding(model_name=scfg.get("model","sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
                            cache_dir=str(ROOT/".cache/fastembed"),threads=2)
    except Exception as e:
        print("FastEmbed unavailable:",e)
        data["semantic_clustered"]=False
        PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); return
    max_items=int(scfg.get("max_items",90))
    subset=items[:max_items]
    texts=["passage: "+((x.get("title") or "")+"\n"+(x.get("content_text") or x.get("summary") or "")[:1800]) for x in subset]
    try:
        vecs=[np.asarray(v,dtype=np.float32) for v in model.embed(texts,batch_size=16)]
    except Exception as e:
        print("embedding failed:",e)
        data["semantic_clustered"]=False
        PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); return
    threshold=float(scfg.get("similarity_threshold",0.90))
    kept=[];kvec=[]
    for item,vec in zip(subset,vecs):
        best_i=-1;best=0.0
        for i,(rep,rv) in enumerate(zip(kept,kvec)):
            if item.get("category")!=rep.get("category"): continue
            sim=cosine(vec,rv)
            if sim>best: best,best_i=sim,i
        if best_i>=0 and best>=threshold: merge(kept[best_i],item)
        else: kept.append(item);kvec.append(vec)
    kept.extend(items[max_items:])
    kept.sort(key=lambda x:(x.get("score",0),x.get("published_at","")),reverse=True)
    data["items"]=kept
    data["semantic_clustered"]=True
    data["semantic_model"]=scfg.get("model")
    data["semantic_merged_count"]=len(items)-len(kept)
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("semantic clusters:",len(items),"->",len(kept))
if __name__=="__main__": main()
