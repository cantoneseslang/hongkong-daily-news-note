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
NOTE_AUTH_STATE: {"cookies": [...], "origins": [...]}  # 2833文字のJSON文字列
```

### NOTE_AUTH_STATE の取得方法
```bash
# ローカルでnote.comにログイン後、認証状態を取得
cat ~/.note-state.json | python3 -c "import json, sys; print(json.dumps(json.load(sys.stdin)))"
```

**重要**: 
- Base64エンコード不要、JSON文字列をそのまま保存
- サイズ: 2833文字（正常）、1005文字（不完全）
- GitHub Secretsに保存する際、全文をコピー&ペーストすること

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
1. **認証状態のサイズを確認**
   ```bash
   # GitHub Actionsログで確認
   📄 認証状態ファイルサイズ: 2833 bytes  # 正常
   📄 認証状態ファイルサイズ: 1005 bytes  # 不完全
   ```
   - 2833文字でない場合、GitHub Secretsの`NOTE_AUTH_STATE`を再設定

2. **Chromiumオプションを確認**
   - `--disable-dev-shm-usage` 必須（GitHub Actions）
   - `--disable-gpu` 必須
   - `--no-sandbox`, `--disable-setuid-sandbox` 必須

3. **ページロード待機を確認**
   - `waitUntil: 'networkidle'` 使用
   - 待機時間: 3秒以上

4. **Viewport & User-Agent設定**
   ```javascript
   viewport: { width: 1280, height: 800 }
   userAgent: 'Mozilla/5.0 ...'
   ```

### 記事が生成されない場合
1. Grok APIキーを確認
2. タイムアウト設定を確認（300秒）
3. `generate_article.py`のログを確認
4. **Grok APIクレジット残高を確認**

### 重複ニュースが多い場合
1. `processed_urls.json`を確認
2. 過去3日分の記事ファイルを確認
3. 重複除外ロジックを確認

---

## 🔧 2025-10-23 修正内容（GitHub Actions対応）

### 問題点
1. headlessモードでnote.comエディターがロードされない
2. 認証状態が正しく復元されない（Base64の問題）
3. タイトル入力欄が見つからない（Timeout）

### 解決策

#### 1. Chromiumオプション追加
```javascript
// note_auto_post.js
const browser = await chromium.launch({
  headless: isCI,  // GitHub Actionsではtrue
  args: [
    '--lang=ja-JP',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',  // ← 追加（重要）
    '--disable-gpu'              // ← 追加
  ],
});
```

#### 2. Context設定追加
```javascript
let contextOptions = {
  locale: 'ja-JP',
  viewport: { width: 1280, height: 800 },  // ← 追加
  userAgent: 'Mozilla/5.0 ...',             // ← 追加
};
```

#### 3. ページロード待機変更
```javascript
// Before
await page.goto('...', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2000);

// After
await page.goto('...', { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(3000);
```

#### 4. 認証状態の保存形式変更
```yaml
# Before: Base64エンコード（GitHub Secretsで文字数制限）
NOTE_AUTH_STATE: ewogICJjb29raWVzIjog...（5048文字）

# After: JSON文字列（そのまま）
NOTE_AUTH_STATE: {"cookies":[...],"origins":[...]}（2833文字）
```

```bash
# ワークフロー内の処理
# Before
echo "$NOTE_AUTH_STATE" | base64 -d > /tmp/.note-state.json

# After
echo "$NOTE_AUTH_STATE" > /tmp/.note-state.json
```

#### 5. タイムアウト延長
```javascript
// タイトル入力欄の待機
await page.waitForSelector('textarea[placeholder*="タイトル"]', { 
  timeout: 30000  // 10秒 → 30秒
});
```

#### 6. 進捗ログ追加
```javascript
// 本文入力の進捗表示（10行ごと）
if (i > 0 && i % 10 === 0) {
  console.log(`  進捗: ${i}/${lines.length}行 (${Math.round(i/lines.length*100)}%)`);
}
```

### 参考
- `post_to_note_github_actions.js` の設定を参照
- 最初から既存の動作コードを確認すべきだった

---

## 📝 今後の改善案（オプション）

- [ ] タグの自動設定
- [ ] 見出し画像の追加
- [ ] カテゴリー別記事分割
- [ ] 通知機能（Discord/Slack）
- [ ] エラー時のリトライ機能強化

