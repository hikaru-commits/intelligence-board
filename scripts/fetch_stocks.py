from __future__ import annotations
import os, json
from pathlib import Path
from datetime import datetime, timezone
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"data/stocks.json"

# Optional Alpha Vantage adapter.
# Set repository secret ALPHAVANTAGE_API_KEY to enable.
SYMBOLS = [
    {"symbol":"5803.T","name":"フジクラ"},
    {"symbol":"6366.T","name":"千代田化工"},
    {"symbol":"9202.T","name":"ANA"},
    {"symbol":"SPCX","name":"SPCX"},
]

def main():
    key = os.getenv("ALPHAVANTAGE_API_KEY","").strip()
    if not key:
        OUT.write_text(json.dumps({
            "updated_at":datetime.now(timezone.utc).isoformat(),
            "status":"APIキー未設定",
            "items":[]
        },ensure_ascii=False,indent=2),encoding="utf-8")
        return

    items=[]
    for s in SYMBOLS:
        try:
            r=requests.get("https://www.alphavantage.co/query",params={
                "function":"GLOBAL_QUOTE","symbol":s["symbol"],"apikey":key
            },timeout=12)
            q=r.json().get("Global Quote",{})
            if not q: continue
            items.append({
                **s,
                "price": q.get("05. price"),
                "change_pct": float(str(q.get("10. change percent","0")).replace("%","") or 0)
            })
        except Exception:
            pass
    OUT.write_text(json.dumps({
        "updated_at":datetime.now(timezone.utc).isoformat(),
        "status":"updated",
        "items":items
    },ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    main()
