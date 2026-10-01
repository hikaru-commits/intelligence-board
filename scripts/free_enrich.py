from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime,timezone
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
PATH=ROOT/"data/news.json"
VERSION="3.0.1"

def sentences(text):
    parts=re.split(r'(?<=[。！？!?])\s*|(?<=[.!?])\s+(?=[A-Z0-9“"])',re.sub(r"\s+"," ",text or "").strip())
    return [p.strip() for p in parts if 35<=len(p.strip())<=650]

def japanese_ratio(s):
    jp=len(re.findall(r"[一-龯ぁ-んァ-ン]",s or "")); en=len(re.findall(r"[A-Za-z]",s or ""))
    return jp/(jp+en+1)

def translator():
    try:
        import argostranslate.translate as tr
        try:return tr.get_translation_from_codes("en","ja")
        except Exception:pass
        import argostranslate.package as pkg
        pkg.update_package_index()
        m=next((p for p in pkg.get_available_packages() if p.from_code=="en" and p.to_code=="ja"),None)
        if m:
            pkg.install_from_path(m.download())
            return tr.get_translation_from_codes("en","ja")
    except Exception as e:print("Argos unavailable",e)
    return None

def ja(tr,s,limit=1200):
    s=(s or "").strip()
    if not s or japanese_ratio(s)>.42 or tr is None:return s
    try:return tr.translate(s[:limit])
    except Exception:return s

def embedder():
    try:
        from fastembed import TextEmbedding
        return TextEmbedding(model_name=CFG["semantic_clustering"]["model"],cache_dir=str(ROOT/".cache/fastembed"),threads=2)
    except Exception as e:print("FastEmbed ranking fallback",e);return None

def select_points(model,title,body,n=3):
    ss=sentences(body)[:CFG["enrichment"]["max_sentences_considered"]]
    if not ss:return []
    if model is None:return ss[:n]
    try:
        vec=[np.asarray(v,dtype=np.float32) for v in model.embed(["query: "+title]+["passage: "+s for s in ss],batch_size=16)]
        q=vec[0]
        scored=[]
        for i,(s,v) in enumerate(zip(ss,vec[1:])):
            sim=float(np.dot(q,v)/((np.linalg.norm(q)*np.linalg.norm(v))+1e-12))
            scored.append((sim+max(0,.08-i*.002),i,s,v))
        # MMR-like diversity: relevance first, then avoid near-duplicate sentences.
        picked=[]
        for cand in sorted(scored,reverse=True):
            if len(picked)>=n:break
            if all(float(np.dot(cand[3],p[3])/((np.linalg.norm(cand[3])*np.linalg.norm(p[3]))+1e-12))<.84 for p in picked):
                picked.append(cand)
        return [p[2] for p in sorted(picked,key=lambda x:x[1])]
    except Exception:return ss[:n]

def clean_title(s,source):
    s=(s or "").strip()
    for sep in (" - "," | "," – "," — "):
        if sep in s:
            a,b=s.rsplit(sep,1)
            if re.sub(r"\W+","",source.lower()) in re.sub(r"\W+","",b.lower()):
                return a.strip()
    return s

def why(x):
    c=x.get("category")
    if c=="IMO・規制":return "規則・検査・船内/会社手順への影響を確認。特に適用対象、発効日、既存船への適用有無を一次資料で確認する価値がある。"
    if c=="海運・LNG":return "LNG船の運航、貨物管理、BOG、代替燃料、機関部設備または将来船仕様の判断材料になり得る。"
    if c=="AI・DX":return "AI開発、Codex、業務自動化、Microsoft系ツールの選定や既存ワークフロー改善につながる可能性がある。"
    if c=="3D・CAD":return "Fusion/Blender/3Dプリントの設計・自動化・FDM製造フロー改善との関連を確認する価値がある。"
    if c=="宇宙":return "衛星・通信・ロケット技術の変化として監視対象。通信・測位・海運へ波及する場合は重要度が上がる。"
    return ""

def signal(x):
    t=(x.get("title_ja") or x.get("title") or "").lower()
    official=x.get("official",False)
    if x.get("category")=="IMO・規制" and official and any(k in t for k in ["発効","施行","改正","採択","amendment","effective","adopted","mepc","marpol","solas","stcw","sire"]):return "HIGH"
    if x.get("category")=="AI・DX" and official and any(k in t for k in ["release","released","launch","introducing","新モデル","codex","claude","gemini","copilot"]):return "HIGH"
    if x.get("cluster_count",1)>=3:return "HIGH"
    return "MEDIUM" if x.get("priority",0)>=4 else "LOW"

def main():
    data=json.loads(PATH.read_text(encoding="utf-8"));items=data.get("items",[])
    tr=translator(); model=embedder();changed=0
    for x in items[:CFG["enrichment"]["max_items_per_run"]]:
        if x.get("free_enrich_version")==VERSION:continue
        title=clean_title(x.get("title",""),x.get("source",""))
        x["title_ja"]=ja(tr,title,500)

        # Do not fabricate summaries from headline-only Google News items.
        body=x.get("content_text","")
        if body:
            pts=select_points(model,title,body,3)
            pts_ja=[ja(tr,p,850) for p in pts]
            pts_ja=[p for i,p in enumerate(pts_ja) if p and all(re.sub(r"\W+","",p.lower())!=re.sub(r"\W+","",q.lower()) for q in pts_ja[:i])]
            x["key_points"]=pts_ja[:3]
            x["summary_ja"]=" ".join(pts_ja[:2])[:340].rstrip()
            x["content_status"]="full"
        else:
            x["summary_ja"]=""
            x["key_points"]=[]
            x["content_status"]="headline"

        x["why_it_matters"]=why(x)
        x["signal"]=signal(x)
        x["free_enrich_version"]=VERSION
        x["free_enriched_at"]=datetime.now(timezone.utc).isoformat()
        x["enrichment_model"]="FastEmbed+Argos+rules"
        changed+=1

    data["version"]="3.0.1-free"
    data["enriched_count"]=sum(bool(x.get("title_ja")) for x in items)
    data["fulltext_enriched_count"]=sum(x.get("content_status")=="full" for x in items)
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"enriched={changed}, titles={data['enriched_count']}, fulltext={data['fulltext_enriched_count']}")

if __name__=="__main__":main()
