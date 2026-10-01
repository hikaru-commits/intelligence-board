# Codex deployment prompt

SignalDeck v2.0 Free を main に反映し、GitHub Actions が成功するまで自律的に修正してください。

絶対条件:
- 有料APIを必須にしない。
- OPENAI_API_KEY / X_BEARER_TOKEN / Tavily / Exa / Firecrawl は不要。
- GitHub Pages + GitHub Actions + OSSだけで標準動作。
- build/deploy失敗時はログ解析→最小修正→再実行。
- validate.pyを必ず通す。
- Pages反映後に UI と生成データを確認。
- JP enriched > 0、full text > 0、semantic_clustered=true を確認。
- demo/example.com を公開しない。
- 巨大画像UIへ戻さない。
