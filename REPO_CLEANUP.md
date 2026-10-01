# 一度だけ削除する旧ファイル

v3反映後、Repository root に残っていれば削除:
- `fetch_news.py`
- `sources.json`
- `fetch_news.cpython-313.pyc`
- `scripts/__pycache__/`

実行系は `scripts/` と `config/` のみです。
Pagesはv3から `_site` だけ公開するため、残っていても公開サイトには出ません。
