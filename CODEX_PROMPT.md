# Codex実装・検証プロンプト

## 目的
このRepositoryを「個人専用ニュース常時表示サイト」として完成させる。
GitHub Actionsが30分ごとに最新ニュースを取得し、GitHub Pagesで会社PC/Mac/iPhone/別Windowsから閲覧可能にする。

## 現状
v0.1 scaffold済み。
- Static frontend: `index.html`, `style.css`, `app.js`
- News fetcher: `scripts/fetch_news.py`
- Optional market fetcher: `scripts/fetch_stocks.py`
- Config: `config/sources.json`
- GitHub Pages workflow: `.github/workflows/update-and-deploy.yml`

## 維持仕様
- 自宅PC常時稼働を前提にしない
- GitHub Pages + GitHub Actions中心
- 30分更新（cron 7,37分）
- 表示は10秒ごとに自動切替
- ブラウザは5分ごとにJSON再読込
- モバイル対応
- Dark UI
- APIキーをコードへ直書きしない
- ニュース更新のたびにmainへcommitを増やさない
- 既存機能を壊さない

## 変更対象
まずRepository全体を監査し、v0.1がGitHub Pages上で確実に動くように修正する。
特に以下を確認:
1. GitHub Actions YAMLのsyntax/permissions/pages deployment
2. Python dependency/version互換性
3. Google News RSS取得
4. RSS entry parsing
5. 画像取得失敗時のfallback
6. `news.json` が0件になった場合の保護
7. XSS/壊れたHTML/不正URL
8. タイムゾーン表示
9. mobile layout
10. cache-busting

## 禁止事項
- React/Next/Vite等へ不要に移行しない
- DBやクラウドサービスをv0.1段階で追加しない
- 有料APIを必須化しない
- APIキーや個人情報をcommitしない
- main branchに30分ごとのdata commitを作らない
- 取得失敗時に既存の正常データを空ファイルで上書きしない

## 実装条件
- エラーのあるfeed/queryが1つあっても全体処理を継続
- 取得結果0件なら既存 `data/news.json` を保持
- HTTP timeoutを設定
- User-Agent設定
- 重複排除
- 日付parse失敗を安全に処理
- 各記事に category / priority / score / title / summary / source / published_at / url / image を持たせる
- 一次情報ドメインはscoreを上げる
- source configの追加だけでカテゴリを増やしやすくする
- UIはニュース画像が無くても崩れない

## 検証方法
ローカルで以下を実施:
1. `python -m pip install -r requirements.txt`
2. `python scripts/fetch_news.py`
3. `python scripts/fetch_stocks.py`
4. JSON schema相当の必須項目チェック
5. `python -m http.server 8080` でブラウザ確認
6. console error無し
7. 10秒自動切替
8. category filter
9. pause/prev/next
10. 5分再読込コード確認
11. 画面幅390px/768px/1440pxで崩れない
12. GitHub Actions workflowを静的に確認

## 完了条件
- `scripts/fetch_news.py` が例外終了せず、実ニュースを1件以上取得
- 取得0件時は既存データ保持
- UIがJSONを読み込み表示
- image有/無の両方で正常表示
- workflowに明らかなsyntax/permission問題なし
- README更新
- 変更点、残課題、検証結果を最後に報告

## 次フェーズ候補（今回は勝手に実装しない）
- IMO/ClassNK/DNV/LR/ABSの専用official-source adapter
- LLM日本語要約
- 日本株/米国株の安定した市場データ取得
- 重大ニュース割り込み
- 保存/後で読む
