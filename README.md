# SignalDeck v3.0 Free Rebuild

無料で継続運用するニュース・インテリジェンスボード。

## v3で再構築したポイント
- 12秒→7秒ローテーション。カードにマウスを置くと一時停止。
- Google News解決を「何でも検索して当てる」方式から、出版社ドメイン一致を必須に変更。
- 間違った記事本文を拾うくらいなら「見出しのみ」と明示する。
- 公式RSSを優先（OpenAI / GitHub / Google / Microsoft / NASA）。
- Trafilatura本文抽出。
- FastEmbed multilingual MiniLMで関連記事統合。
- Argos Translateで無料の英日翻訳。
- 本文取得記事だけ要約・KEY POINTSを生成。
- HIGH判定を抑制し、公式か複数ソース裏付けを重視。
- MARKETは有料/不安定APIを標準から外し、データが無いとUIごと非表示。
- GitHub PagesへRepository全体ではなく `_site` だけを公開。
- validatorで「公式記事なのに別ドメイン本文」の混入をビルド失敗にする。

## 無料構成
GitHub Pages + GitHub Actions + RSS/Atom + Trafilatura + FastEmbed + Argos Translate。

OpenAI API / X API / Tavily / Exa / Firecrawl / Alpha Vantage は必須ではありません。

## 品質思想
本文を取得できないニュースについて、タイトルを要約として繰り返しません。
「見出しのみ」と表示し、誤った本文・誤要約を作らないことを優先します。
