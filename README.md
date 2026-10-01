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
