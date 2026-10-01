# SignalDeck v3 deployment / PDCA

このフォルダの内容で `hikaru-commits/intelligence-board` を更新してください。

必須:
1. v3ファイルを同じパスへ反映。
2. rootの `fetch_news.py`, `sources.json`, `fetch_news.cpython-313.pyc`, `scripts/__pycache__` を削除。
3. GitHub Actions `Build SignalDeck v3 Free` を実行。
4. 失敗したらログを読み、原因を直して再実行。
5. 成功後のログで fetch / cluster / enrich / validate / build_site を確認。
6. Pagesの `data/news.json` で以下を検証:
   - version = 3.0-free
   - enriched_count > 0
   - content_extracted_count > 0 が望ましい。ただし0でも誤った本文を採用しないことを優先。
   - full-text記事のURL domainが expected_domain と一致。
7. UI確認:
   - 自動切替7秒
   - hover中は停止
   - 見出しのみ記事で重複KEY POINTSを出さない
   - 本文取得済記事で要約とKEY POINTSが表示
   - MARKETデータなしなら欄を非表示
   - 巨大画像に戻っていない

絶対条件:
- 有料APIを必須にしない。
- 本文取得率を上げるために出版社不一致URLを採用しない。
- 成功するまで修正→再検証を繰り返す。
