from __future__ import annotations
import json, re, os, math
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
PATH = ROOT/"data/news.json"

STOP_EN = {
    "the","a","an","and","or","of","to","in","on","for","with","by","from","as","at","is","are","was","were",
    "be","been","being","that","this","these","those","it","its","into","over","under","after","before","about",
    "new","latest","says","say","said","will","can","could","would","may","more","than","their","they","we","you"
}
STOP_JA = {"する","した","して","いる","ある","なる","ため","こと","これ","それ","など","について","による","及び"}

def split_sentences(text:str):
    text = re.sub(r"\s+"," ",text or "").strip()
    if not text:
        return []
    # English/Japanese sentence segmentation without heavyweight NLP.
    parts = re.split(r'(?<=[。！？!?])\s*|(?<=[.!?])\s+(?=[A-Z0-9“"])', text)
    out=[]
    for p in parts:
        p=p.strip()
        if len(p) >= 25:
            out.append(p)
    return out

def tokens(text:str):
    eng = re.findall(r"[A-Za-z][A-Za-z0-9+\-\.]{1,}", text.lower())
    ja = re.findall(r"[一-龯ぁ-んァ-ン]{2,}", text)
    return [x for x in eng if x not in STOP_EN] + [x for x in ja if x not in STOP_JA]

def extractive_points(text:str, title:str, n=3):
    sents = split_sentences(text)
    if not sents:
        return []
    freq = Counter(tokens(text + " " + title))
    scored=[]
    for i,s in enumerate(sents[:40]):
        ts=tokens(s)
        if not ts:
            continue
        score=sum(freq[t] for t in set(ts))/max(6,len(ts))
        # prefer early sentences and sentences with numbers / concrete entities
        score += max(0,1.2-i*0.04)
        if re.search(r"\b\d+(?:\.\d+)?%?\b",s):
            score += .4
        if any(k.lower() in s.lower() for k in ["launch","release","regulation","amendment","effective","approved","adopted","rule","model","LNG","IMO","MARPOL","SOLAS","STCW"]):
            score += .45
        scored.append((score,i,s))
    picked=sorted(scored,reverse=True)[:n]
    return [x[2] for x in sorted(picked,key=lambda x:x[1])]

def ensure_argos():
    try:
        import argostranslate.translate as tr
        # already installed?
        try:
            return tr.get_translation_from_codes("en","ja")
        except Exception:
            pass
        import argostranslate.package as pkg
        pkg.update_package_index()
        avail = pkg.get_available_packages()
        model = next((p for p in avail if p.from_code=="en" and p.to_code=="ja"),None)
        if not model:
            return None
        path=model.download()
        pkg.install_from_path(path)
        return tr.get_translation_from_codes("en","ja")
    except Exception as e:
        print("Argos unavailable:",e)
        return None

def mostly_japanese(text):
    if not text:
        return False
    jp=len(re.findall(r"[一-龯ぁ-んァ-ン]",text))
    latin=len(re.findall(r"[A-Za-z]",text))
    return jp > latin*.35

def translate(translator,text,max_chars=1200):
    text=(text or "").strip()
    if not text or mostly_japanese(text) or translator is None:
        return text
    text=text[:max_chars]
    try:
        return translator.translate(text)
    except Exception:
        return text

def dedupe_points(points):
    out=[]
    seen=set()
    for p in points:
        p=(p or "").strip()
        if not p: continue
        key=re.sub(r"\W+","",p.lower())
        if not key or key in seen: continue
        if any((key in old or old in key) and min(len(key),len(old))/max(len(key),len(old))>.80 for old in seen):
            continue
        seen.add(key); out.append(p)
    return out

def why_it_matters(item):
    cat=item.get("category","")
    title=(item.get("title_ja") or item.get("title") or "").lower()
    text=(item.get("summary_ja") or item.get("summary") or "").lower()
    both=title+" "+text
    if cat=="IMO・規制":
        if any(k.lower() in both for k in ["発効","施行","改正","amendment","effective","regulation","mepc","marpol","solas","stcw","sire"]):
            return "規則・検査・船内手順・会社手順への反映要否を確認する価値が高い。適用対象と発効日を元記事で確認。"
        return "海運実務への適用可否を確認する候補。一次資料と適用対象の確認が必要。"
    if cat=="海運・LNG":
        return "LNG船運航、代替燃料、機関部設備、燃料効率や将来船仕様の判断材料になり得る。"
    if cat=="AI・DX":
        if any(k in both for k in ["codex","claude code","copilot","mcp","agent","モデル","model"]):
            return "AI開発・業務自動化・Codex運用の改善やツール選定に直接使える可能性がある。"
        return "AI/DXの実務適用候補。既存ワークフローへ置き換え可能かを見る価値がある。"
    if cat=="3D・CAD":
        return "3Dモデリング、Fusion/Blender、自動生成、FDM印刷ワークフローの効率化に関係する可能性がある。"
    if cat=="宇宙":
        return "衛星・通信・ロケット技術の進展として監視価値がある。海運や通信への波及がある場合は優先度が上がる。"
    return "関心分野との関連を確認する候補。"

def rule_signal(item):
    cat=item.get("category","")
    t=((item.get("title_ja") or item.get("title") or "")+" "+(item.get("summary_ja") or item.get("summary") or "")).lower()
    high_terms=["発効","施行","採択","改正","重大","launch","released","release","effective","adopted","amendment","new model","新モデル"]
    if cat=="IMO・規制" and any(x.lower() in t for x in high_terms+["mepc","marpol","solas","stcw","sire"]):
        return "HIGH"
    if cat=="AI・DX" and any(x.lower() in t for x in high_terms+["codex","claude code","gemini","copilot","mcp"]):
        return "HIGH"
    if item.get("priority",0)>=4:
        return "MEDIUM"
    return "LOW"

def main():
    data=json.loads(PATH.read_text(encoding="utf-8"))
    items=data.get("items",[])
    limit=int(CFG.get("enrichment",{}).get("max_items_per_run",18))
    translator=ensure_argos()
    enriched=0

    for item in items:
        if enriched>=limit:
            break
        # Keep cached enrichment unless article changed/new.
        if item.get("free_enriched_at") and item.get("title_ja") and item.get("summary_ja"):
            continue

        source_text=item.get("content_text") or item.get("summary") or ""
        points=extractive_points(source_text,item.get("title",""),3)
        if not points and item.get("summary"):
            points=[item["summary"]]

        title_ja=translate(translator,item.get("title",""),400)
        translated_points=[translate(translator,p,650) for p in points[:3]]

        # summary is first 1-2 strongest/earliest selected sentences, not title paraphrase
        summary_ja=" ".join(translated_points[:2]).strip()
        if len(summary_ja)>260:
            summary_ja=summary_ja[:257].rstrip()+"…"

        item["title_ja"]=title_ja
        item["summary_ja"]=summary_ja or translate(translator,item.get("summary",""),900)
        item["key_points"]=[p[:180] for p in translated_points if p][:3]
        if not item["key_points"] and item.get("summary_ja"):
            item["key_points"]=[item["summary_ja"][:180]]
        item["why_it_matters"]=why_it_matters(item)
        item["signal"]=rule_signal(item)
        item["free_enriched_at"]=datetime.now(timezone.utc).isoformat()
        item["enrichment_model"]="Argos+extractive-rules"
        enriched+=1

    data["version"]="2.0.1-free"
    data["enriched_count"]=sum(1 for x in items if x.get("title_ja"))
    data["enrichment_mode"]="free-local"
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("free-enriched",enriched,"items; total",data["enriched_count"])

if __name__=="__main__":
    main()
