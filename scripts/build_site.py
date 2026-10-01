from pathlib import Path
import shutil,json
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/"_site"
if SITE.exists():shutil.rmtree(SITE)
(SITE/"data").mkdir(parents=True)
for name in ("index.html","style.css","app.js"):
    shutil.copy2(ROOT/name,SITE/name)
for name in ("news.json","stocks.json"):
    shutil.copy2(ROOT/"data"/name,SITE/"data"/name)
(SITE/".nojekyll").write_text("",encoding="utf-8")
print("site files:",sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*") if p.is_file()))
