# 🚀 GitHub Actions 自動化セットアップガイド

毎日朝6時（JST/HKT）に自動でニュース記事を生成する完全自動化の設定方法です。

## 📋 前提条件

- ✅ GitHubリポジトリ: https://github.com/cantoneseslang/kirii-net
- ✅ GitHub Personal Access Token (PAT): 取得済み
- ✅ Grok API Key: 取得済み

## 🔐 ステップ1: GitHub Secretsの設定

### 1. GitHubリポジトリのSecretsページにアクセス

```
https://github.com/cantoneseslang/kirii-net/settings/secrets/actions
```

### 2. 以下のSecretsを追加

**「New repository secret」** をクリックして、以下を1つずつ追加：

#### GROK_API_KEY
- **Name**: `GROK_API_KEY`
- **Value**: `config.jsonから取得したGrok API Key`

#### NEWS_API_KEY（オプション - 現在は未使用）
- **Name**: `NEWS_API_KEY`
- **Value**: `config.jsonから取得したNews API Key`

#### WORLD_NEWS_API_KEY（オプション - 現在は未使用）
- **Name**: `WORLD_NEWS_API_KEY`
- **Value**: `config.jsonから取得したWorld News API Key`

#### NEWSDATA_IO_API_KEY（オプション - 現在は未使用）
- **Name**: `NEWSDATA_IO_API_KEY`
- **Value**: `config.jsonから取得したNewsdata.io API Key`

### 3. 確認

Secretsページに4つのシークレットが追加されていることを確認してください。

## 📝 ステップ2: .gitignoreの更新

生成された記事ファイル（.md）をGitにコミットできるように、.gitignoreを修正します：

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note

# .gitignoreを編集
# 以下の行を変更:
# daily-articles/*.md
# ↓
# daily-articles/rss_news_*.json
# daily-articles/raw_news_*.json
```

または、以下のコマンドで自動修正：

```bash
sed -i.bak 's/daily-articles\/\*\.md/# daily-articles\/*.md (記事ファイルはコミット)/' .gitignore
```

## 🚀 ステップ3: GitHub Actionsワークフローをプッシュ

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note

# 変更をコミット
git add .github/workflows/daily-news.yml
git add .gitignore
git commit -m "🤖 Add GitHub Actions workflow for daily news automation"
git push origin main
```

## ✅ ステップ4: ワークフローの確認

### 1. GitHub Actionsページにアクセス

```
https://github.com/cantoneseslang/kirii-net/actions
```

### 2. 「Daily Hong Kong News Generator」ワークフローを確認

### 3. 手動でテスト実行

- 「Run workflow」ボタンをクリック
- 「Run workflow」を再度クリックして実行

### 4. 実行ログを確認

- 実行中のワークフローをクリック
- 各ステップの詳細ログを確認

## ⏰ 実行スケジュール

- **自動実行**: 毎日 UTC 22:00（JST 07:00 / HKT 06:00）
- **手動実行**: GitHub Actionsページからいつでも実行可能

## 📊 実行フロー

1. **RSS取得**: 140件程度のニュースを取得
2. **重複チェック**: 過去3日分の記事と比較
3. **記事生成**: Grok APIで30件の日本語記事を生成
4. **日付修正**: タイトルの日付を自動で当日に修正
5. **自動コミット**: 生成された記事をリポジトリに自動プッシュ

## 🔧 トラブルシューティング

### ワークフローが失敗する場合

1. **Secretsを確認**
   - GROK_API_KEYが正しく設定されているか確認

2. **ログを確認**
   - GitHub Actionsページでエラーログを確認

3. **手動でテスト**
   ```bash
   cd /Users/sakonhiroki/hongkong-daily-news-note
   source venv/bin/activate
   python fetch_rss_news.py
   python generate_article.py daily-articles/rss_news_*.json
   ```

### 実行時刻を変更したい場合

`.github/workflows/daily-news.yml` の以下を編集：

```yaml
schedule:
  - cron: '0 22 * * *'  # UTC 22:00 = JST 07:00
```

変更例：
- JST 08:00に実行: `'0 23 * * *'`  # UTC 23:00
- JST 07:00に実行: `'0 22 * * *'`  # UTC 22:00

## 📮 note.comへの投稿

記事生成後、手動で投稿：

```bash
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js /Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_$(date +%Y-%m-%d).md
```

または、リポジトリから最新記事を取得：

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
git pull origin main
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js /Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_$(date +%Y-%m-%d).md
```

## 🎉 完了

これで、毎日朝6時に自動で：
1. ✅ RSSフィードからニュースを取得
2. ✅ 過去3日分と重複チェック
3. ✅ 30件の日本語記事を生成
4. ✅ 正しい日付で自動保存
5. ✅ GitHubリポジトリに自動プッシュ

が完全自動で実行されます！🚀

## 📧 通知設定（オプション）

GitHub Actionsの実行結果をメールで受け取りたい場合：

1. GitHub設定 → Notifications
2. 「Actions」セクションで通知を有効化

## 🔗 参考リンク

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Encrypted secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

