# SignalDeck v2.0 Free

無料OSSだけで常用するインテリジェンスダッシュボード。

収集 → Trafilatura本文抽出 → FastEmbed意味クラスタリング → Argos英日翻訳 → ルールベース重要度/関連性 → GitHub Pages。

標準運用でOpenAI API、X API、Tavily、Exa、Firecrawlは不要です。

採用:
- Trafilatura 2.2.0
- FastEmbed 0.8.1
- intfloat/multilingual-e5-small
- Argos Translate 1.11.0
- feedparser / BeautifulSoup
- RSSHub optional

外部ニュースを商用再配信する場合は、各情報源の利用規約・著作権・再配信条件を別途確認してください。


## v2.0.1 hotfix
- Google News RSSのラップURLを `googlenewsdecoder 0.2.1` で元記事URLへ解決してからTrafilaturaへ渡す。
- FastEmbed標準対応の multilingual MiniLM モデルへ変更。
- KEY POINTSの重複を抑制。


## v2.0.2 hotfix
- googlenewsdecoder 0.2.1 の現行レスポンス `success` に対応。
- decode成功/失敗件数をActionsログへ表示。
- KEY POINTS重複除去を実際の生成処理へ適用。
- タイトルと同一の「要約」は表示しない。


## v2.0.3 hotfix
- Google News RSSでは summary 内リンクより canonical entry.link を優先。
- `news.google.com/rss/articles/...` を元記事URLへdecodeしてからTrafilaturaへ渡す。
- 古い日本語化キャッシュを一度無効化し、全記事をv2.0.3ロジックで再生成。
- KEY POINTS重複除去・タイトルコピー要約抑制を既存記事にも反映。


## v2.1 — Resolver architecture
Google News decoderだけに依存する方式を廃止。
本文取得時に以下の無料fallbackを順番に使います。

1. 既存の直接URL
2. Google News URL decode
3. Bing RSSで記事タイトル完全一致検索
4. 候補URLをTrafilaturaで実際に本文抽出できるか検証

記事本文が取れないURLは採用しません。
Actionsログに attempted / resolved / extracted 件数を出します。
