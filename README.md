# SignalDeck v1.2 Free

SignalDeckの完全無料運用版です。
OpenAI API、X API、有料検索APIを標準構成から外し、GitHub Actions + OSSだけで更新します。

## 無料構成
- GitHub Pages: 公開UI
- GitHub Actions: 30分ごとの自動更新
- Google News RSS / 公式サイト検索: ニュース発見
- RSSHub: 任意の追加フィード（自前または無料インスタンス利用時）
- Trafilatura: 元記事本文抽出
- Argos Translate: 英語→日本語のオフライン翻訳
- 自作Extractive Summarizer: 本文から重要文抽出
- 自作Rule Engine: KEY POINTS / WHY IT MATTERS / SIGNAL
- 文字n-gram + タイトル類似度: 無料の関連記事クラスタリング

## 有料APIは不要
`OPENAI_API_KEY` は使いません。
`X_BEARER_TOKEN` も使いません。

Xの話題監視は、将来RSSHub routeまたは検索エンジンで取得可能な公開情報を使う方式へ寄せます。
X公式APIが必要な機能は標準無料版では無効です。

## 翻訳
Argos Translateの英→日モデルをGitHub Actions初回実行時に取得し、その後はGitHub Actions Cacheで再利用します。
Argos Translateはオープンソースのオフライン翻訳ライブラリです。

## AI要約の代替
生成AIによる要約ではなく、Trafilaturaで取得した本文から重要文をスコアリングして抽出します。

1. 本文を文分割
2. 頻出キーワード
3. 冒頭優先度
4. 数値・規制・release等の重要語
5. 上位2〜3文を抽出
6. 英文ならArgosで日本語化

このため、生成AIより文章の自然さは劣りますが、事実を勝手に補完しにくく、費用は0円です。

## WHY IT MATTERS
LLMではなくカテゴリ別ルールで作成します。
- IMO・規制 → 規則/検査/会社手順への影響
- 海運・LNG → LNG船/代替燃料/設備/効率
- AI・DX → Codex/AI自動化/開発
- 3D・CAD → Fusion/Blender/FDM
- 宇宙 → 衛星/通信/技術動向

## セマンティッククラスタリング
有料Embedding APIは使用しません。
タイトル類似度と文字3-gram Jaccard類似度で近い記事を束ねます。

## RSSHub
任意です。使わなくてもSignalDeckは動きます。

GitHub Variable:
`RSSHUB_BASE_URL`

routeは `config/sources.json` の `rsshub.routes` に追加します。

## 株価
現在のAlpha Vantageは任意です。
完全無料・APIキーなしに統一したい場合はMARKET欄をOFFにできます。
市場データは別途、無料かつ安定した取得元を再選定します。

## 更新
GitHub Actions:
毎時 07分 / 37分

## 品質上の注意
完全無料版は生成AI版より翻訳の自然さ、意味理解、関連記事統合精度が落ちます。
その代わり、継続運用コスト0円・API課金なし・外部LLMへの記事本文送信なしを優先しています。
