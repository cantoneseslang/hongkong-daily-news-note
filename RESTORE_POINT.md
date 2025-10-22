# 🎯 デイリーニュース自動化 - 復元ポイント

## ✅ 完全動作確認済み設定（v1.0）

**作成日時**: 2025-10-22  
**Git Tag**: `v1.0-working-automation`  
**状態**: ローカル＆GitHub Actions完全動作確認済み

---

## 📋 システム構成

### 自動化フロー（毎日朝6時 JST）
```
1. RSS取得 (fetch_rss_news.py)
   ↓
2. 記事生成 (generate_article.py) ← Grok API
   ↓
3. GitHubプッシュ
   ↓
4. note.com投稿 (note_auto_post.js) ← Playwright
```

---

## 🔑 重要ファイル

### 1. ワークフロー
- **ファイル**: `.github/workflows/daily-news.yml`
- **トリガー**: 
  - `push` (main branch)
  - `schedule` (cron: '0 22 * * *' = JST 6:00)
  - `workflow_dispatch` (手動実行)

### 2. note.com投稿スクリプト（専用）
- **ファイル**: `note_auto_post.js`
- **元ソース**: `/Users/sakonhiroki/note-post-mcp/auto-login-and-draft.js`
- **重要な修正点**:
  ```javascript
  function loadUrls() {
    // ファイルがなければ空のオブジェクトを返す（画像なしでも動作）
    if (!existsSync(urlsPath)) {
      return {};
    }
    // ...
  }
  ```
- **特徴**:
  - 認証状態保存対応（GitHub Actionsでは使用しない）
  - 画像なし対応
  - タグ設定対応（このプロジェクトでは未使用）

### 3. 記事生成
- **ファイル**: `generate_article.py`
- **API**: Grok API (timeout: 300秒)
- **重複除外**: 過去3日分のURLとタイトル比較

### 4. RSS取得
- **ファイル**: `fetch_rss_news.py`
- **タイムアウト**: 5秒
- **スリープ**: 0.5秒
- **取得期間**: 過去48時間

---

## 🔧 復元方法

### 完全復元
```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
git fetch --tags
git checkout v1.0-working-automation
```

### 特定ファイルのみ復元
```bash
# note投稿スクリプト
git checkout v1.0-working-automation -- note_auto_post.js

# ワークフロー
git checkout v1.0-working-automation -- .github/workflows/daily-news.yml

# 全主要ファイル
git checkout v1.0-working-automation -- \
  note_auto_post.js \
  .github/workflows/daily-news.yml \
  fetch_rss_news.py \
  generate_article.py
```

---

## 📦 必須依存関係

### Python (3.11+)
```bash
pip install -r requirements.txt
```
- feedparser
- requests
- python-dateutil

### Node.js (20+)
```bash
npm install
npx playwright install chromium
```
- playwright (^1.40.0)

---

## 🔐 GitHub Secrets（必須）

```yaml
GROK_API_KEY: xai-***
NOTE_EMAIL: bestinksalesman
NOTE_PASSWORD: Hsakon0419
```

---

## ⚠️ 重要な注意事項

### このプロジェクト専用の特徴
1. **画像は使用しない** - テキストニュースのみ
2. **タグは未使用** - 将来的に追加可能
3. **見出し画像なし**
4. **認証状態ファイル不要**（GitHub Actions環境）

### 他のnote投稿プロジェクトとの違い
- `/Users/sakonhiroki/note-post-mcp/`: 画像・タグ・見出し画像あり
- このプロジェクト: テキストのみのシンプル版

### 絶対に変更してはいけないもの
1. `note_auto_post.js`の`loadUrls()`関数（existsCheckあり）
2. ワークフローの実行順序（記事生成→プッシュ→投稿）
3. Playwrightのバージョン（1.40.0）

---

## 🧪 ローカルテスト方法

### 記事生成のみ
```bash
python fetch_rss_news.py
python generate_article.py daily-articles/rss_news_*.json
```

### note投稿のみ
```bash
node note_auto_post.js \
  daily-articles/hongkong-news_2025-10-22.md \
  bestinksalesman \
  Hsakon0419
```

### 全フロー
```bash
python scheduler.py
```

---

## 📊 動作確認済み環境

### ローカル
- macOS 24.6.0
- Python 3.13
- Node.js 20.x
- Playwright 1.40.0

### GitHub Actions
- ubuntu-latest
- Python 3.11.13
- Node.js 20.19.5
- Playwright 1.40.0

---

## 🚨 トラブルシューティング

### note投稿が失敗する場合
1. GitHub Secretsを確認
2. Playwrightのバージョンを確認
3. `note_auto_post.js`が正しいか確認
4. タグ `v1.0-working-automation` から復元

### 記事が生成されない場合
1. Grok APIキーを確認
2. タイムアウト設定を確認（300秒）
3. `generate_article.py`のログを確認

### 重複ニュースが多い場合
1. `processed_urls.json`を確認
2. 過去3日分の記事ファイルを確認
3. 重複除外ロジックを確認

---

## 📝 今後の改善案（オプション）

- [ ] タグの自動設定
- [ ] 見出し画像の追加
- [ ] カテゴリー別記事分割
- [ ] 通知機能（Discord/Slack）
- [ ] エラー時のリトライ機能強化

