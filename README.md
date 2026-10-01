# Personal Intelligence Board v0.3

海運・IMO規制・AI/DX・3D/CAD・宇宙など、指定分野の最新ニュースを
GitHub Actionsで30分ごとに取得し、GitHub Pagesで常時表示する個人向けダッシュボードです。

## v0.1 の狙い
- 自宅PCを24時間稼働させない
- GitHub Actions側で30分ごとにニュース取得
- GitHub Pagesなので会社PC / Mac / iPhone / 別Windowsから同じURLで閲覧
- 画面は10秒ごとにニュースを自動切替
- ブラウザは5分ごとに最新 `news.json` を再読込
- ニュースデータをGitに30分ごとにcommitしない（Pages artifactへ直接生成）

## 最短セットアップ
1. GitHubで新規Repositoryを作成（例: `intelligence-board`）
2. このフォルダの中身をRepositoryへpush
3. GitHub: Settings → Pages → Source を `GitHub Actions`
4. Actionsタブで `Update feeds and deploy Pages` を手動実行
5. 成功後、Pages URLを開く

以後は `7分 / 37分` に自動更新します。
GitHub scheduled workflowは厳密な実行時刻保証ではないため、多少遅延する場合があります。

## ローカル確認
`file://` 直開きではfetchが制限されるブラウザがあります。

```powershell
py -m http.server 8080
```

その後:
`http://localhost:8080`

ニュース取得もローカルで試す場合:

```powershell
py -m pip install -r requirements.txt
py scripts\fetch_news.py
py -m http.server 8080
```

## ニュースカテゴリ変更
`config/sources.json` の `categories[].queries` を編集します。

## 株価
v0.1ではニュース部分を先に安定させています。
株価は `ALPHAVANTAGE_API_KEY` がGitHub Repository Secretに設定されている場合のみ取得します。
無料枠・対象市場・リアルタイム性には制限があるため、後続版で日本株向けデータ源を別評価して差し替える前提です。

Repository:
Settings → Secrets and variables → Actions → New repository secret

Name:
`ALPHAVANTAGE_API_KEY`

## 現在の既知制約
- Google News RSSの記事リンクはGoogle News経由になる場合があります。
- 記事画像はOGP取得に失敗するサイトがあり、その場合は画像なし表示になります。
- 自動要約は現時点ではRSS本文ベースです。API課金なしで運用するため、LLM要約はまだ入れていません。
- IMO公式はRSS案内ページが存在しますが、2026-10-01確認時点でPress Briefingsのリンク先が404でした。
  そのためv0.1では検索RSS側でIMO関連を拾い、後続でIMO専用adapterを追加します。
- 公開Repositoryの場合、サイトや設定ファイルは公開されます。秘密情報/APIキーは必ずGitHub Secretsに入れてください。

## 次の優先実装
1. IMO / ClassNK / DNV / LR / ABS 等の公式ソース専用adapter
2. 一次情報を優先するランキング
3. 日本語3行要約（低コストLLMまたはルールベース）
4. 株価データ源の再選定
5. 「必須 / 興味 / 一般」の表示レーン
6. 保存・後で読む
7. 新着重大ニュースの割り込み表示


## v0.2 changes
- IMO / ClassNK / DNV / LR / ABS / OCIMF / OpenAI / Microsoft / GitHub / Autodesk / Bambu Lab / NASA の公式ドメイン優先レーンを追加
- 公式ソースはランキングを強く優遇
- RSS本文に含まれる元記事URLを可能な範囲で抽出
- Google Newsの汎用画像を除外し、元記事OGP画像を優先
- 類似見出しをクラスタリングして重複表示を削減
- 関連記事件数を画面表示
- 取得0件時は正常な既存news.jsonを空データで上書きしない

日本語LLM要約は有料APIを必須化しないため、まだ必須機能にはしていません。


## v0.3 changes
- メイン画像を24%程度まで縮小し、見出し・本文を主役に変更
- 画像がない記事は画像領域そのものを非表示にし、見出しを全幅表示
- AI監視対象を OpenAI / Claude / Gemini / Copilot / Cursor / Windsurf / MCP / Agent Skills / Computer Use / 生成AI / ローカルLLM まで拡張
- `github.com` 全体を公式扱いする誤判定を廃止し、`github.blog` をGitHub公式として扱う
- X API Recent Search対応を追加（`X_BEARER_TOKEN` が設定されている場合のみ）
- XではAIキーワードの日本語・英語検索に加え `@Sokichi_Hoshino` を監視対象に追加
- X投稿はいいね・リポスト・返信・引用を加味した話題度で上位を選定
- 表示ラベルを「公式 / 報道 / X話題」に分離

### X監視を有効化
GitHub Repository:
Settings → Secrets and variables → Actions → New repository secret

Name:
`X_BEARER_TOKEN`

Value:
X Developer Consoleで作成したAppのBearer Token

Xトークンが未設定でもニュースサイト本体は正常動作します。
