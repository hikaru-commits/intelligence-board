from pathlib import Path
from datetime import datetime,timezone
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/stocks.json"
# v3 deliberately ships without a brittle or paid market API.
# UI hides this section when no trusted feed is configured.
OUT.write_text(json.dumps({
  "updated_at":datetime.now(timezone.utc).isoformat(),
  "status":"disabled-free-default",
  "items":[]
},ensure_ascii=False,indent=2),encoding="utf-8")
