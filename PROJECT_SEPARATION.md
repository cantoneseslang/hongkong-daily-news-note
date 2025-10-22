# 📂 プロジェクト棲み分けガイド

## 🎯 プロジェクト一覧

### 1. 📰 香港デイリーニュース（このプロジェクト）
**パス**: `/Users/sakonhiroki/hongkong-daily-news-note/`

**目的**: 香港ニュースの自動収集・記事生成・note投稿

**記事保存先**: 
```
/Users/sakonhiroki/hongkong-daily-news-note/daily-articles/
├── hongkong-news_2025-10-22.md
├── hongkong-news_2025-10-21.md
└── ...
```

**特徴**:
- ✅ **完全自動化**（毎日朝6時）
- ✅ RSSからニュース取得
- ✅ Grok APIで記事生成
- ✅ 重複除外あり
- ✅ テキストのみ（画像なし）
- ✅ タグなし

**使用スクリプト**:
- `fetch_rss_news.py` - RSS取得
- `generate_article.py` - 記事生成
- `note_auto_post.js` - note投稿（専用）

---

### 2. 📝 広東語記事投稿（別プロジェクト）
**パス**: `/Users/sakonhiroki/note-post-mcp/`

**目的**: 広東語学習記事・その他の記事をnoteに投稿

**記事例**:
```
/Users/sakonhiroki/note-post-mcp/
├── cantonese-100-phrases.md
├── cantonese-business-30.md
├── cantonese-app-thumbnail.png
└── images/
```

**特徴**:
- ✅ **手動投稿**
- ✅ 画像あり
- ✅ タグあり（`#今日の広東語` など）
- ✅ 見出し画像あり
- ✅ 画像URLマッピング（`images/urls.txt`）

**使用スクリプト**:
- `auto-login-and-draft.js` - 汎用投稿スクリプト

---

## 🔀 完全な棲み分け

### ディレクトリ構造
```
/Users/sakonhiroki/
├── hongkong-daily-news-note/          ← デイリーニュース専用
│   ├── daily-articles/                ← 記事はここ
│   │   ├── hongkong-news_*.md
│   │   └── rss_news_*.json
│   ├── note_auto_post.js              ← テキストのみ投稿
│   ├── fetch_rss_news.py
│   ├── generate_article.py
│   └── .github/workflows/
│
└── note-post-mcp/                     ← 広東語記事専用
    ├── cantonese-*.md                 ← 記事はここ
    ├── images/                        ← 画像はここ
    │   ├── *.png
    │   └── urls.txt
    └── auto-login-and-draft.js        ← 画像・タグ対応
```

---

## 🎯 使い分けルール

### Cursor起動時の確認方法

#### デイリーニュースをチェックしたい時
```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
```

**確認ポイント**:
- `daily-articles/` に記事がある
- `note_auto_post.js` がある
- `.github/workflows/` がある

#### 広東語記事をチェックしたい時
```bash
cd /Users/sakonhiroki/note-post-mcp
```

**確認ポイント**:
- `cantonese-*.md` ファイルがある
- `images/` ディレクトリがある
- `auto-login-and-draft.js` がある

---

## 📋 機能比較表

| 機能 | デイリーニュース | 広東語記事 |
|------|------------------|------------|
| **ディレクトリ** | `hongkong-daily-news-note/` | `note-post-mcp/` |
| **記事保存先** | `daily-articles/` | ルート直下 |
| **自動実行** | ✅ GitHub Actions | ❌ 手動 |
| **画像** | ❌ なし | ✅ あり |
| **タグ** | ❌ なし | ✅ あり |
| **見出し画像** | ❌ なし | ✅ あり |
| **投稿スクリプト** | `note_auto_post.js` | `auto-login-and-draft.js` |
| **記事生成** | ✅ Grok API | ❌ 手動作成 |
| **ニュース取得** | ✅ RSS自動 | ❌ なし |

---

## 🔧 実行コマンド

### デイリーニュース

#### ローカルで記事生成
```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
python fetch_rss_news.py
python generate_article.py daily-articles/rss_news_*.json
```

#### note投稿
```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
node note_auto_post.js \
  daily-articles/hongkong-news_2025-10-22.md \
  bestinksalesman \
  Hsakon0419
```

### 広東語記事

#### note投稿
```bash
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js cantonese-100-phrases.md
```

---

## ⚠️ 重要な注意事項

### 絶対にやってはいけないこと

1. **スクリプトの混同**
   - ❌ `hongkong-daily-news-note/` で `auto-login-and-draft.js` を使う
   - ❌ `note-post-mcp/` で `note_auto_post.js` を使う

2. **記事ファイルの混在**
   - ❌ デイリーニュース記事を `note-post-mcp/` に保存
   - ❌ 広東語記事を `daily-articles/` に保存

3. **設定ファイルの混同**
   - ❌ `config.json` を両プロジェクトで共有
   - ❌ `.note-state.json` を両プロジェクトで共有

---

## 🔍 Cursor起動時のチェックリスト

### デイリーニュース作業の場合

```bash
# 1. ディレクトリ確認
pwd
# 出力: /Users/sakonhiroki/hongkong-daily-news-note

# 2. 最新記事確認
ls -lt daily-articles/hongkong-news_*.md | head -3

# 3. スクリプト確認
ls note_auto_post.js
```

### 広東語記事作業の場合

```bash
# 1. ディレクトリ確認
pwd
# 出力: /Users/sakonhiroki/note-post-mcp

# 2. 記事確認
ls -lt cantonese-*.md | head -3

# 3. スクリプト確認
ls auto-login-and-draft.js
```

---

## 📊 依存関係

### デイリーニュース
```json
{
  "python": ["feedparser", "requests", "python-dateutil"],
  "node": ["playwright@1.40.0"],
  "secrets": ["GROK_API_KEY", "NOTE_EMAIL", "NOTE_PASSWORD"]
}
```

### 広東語記事
```json
{
  "python": [],
  "node": ["playwright"],
  "secrets": []
}
```

---

## 🎓 まとめ

### デイリーニュース = 完全自動化
- **ワークフロー**: RSS → 記事生成 → GitHubプッシュ → note投稿
- **保存先**: `daily-articles/`
- **特徴**: テキストのみ、タグなし、自動実行

### 広東語記事 = 手動投稿
- **ワークフロー**: 記事作成 → 画像準備 → 手動投稿
- **保存先**: `note-post-mcp/` ルート
- **特徴**: 画像あり、タグあり、手動実行

---

## 🚀 復元方法（混乱した場合）

### デイリーニュースを確実に動かす
```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
git checkout v1.0-working-automation
```

### 広東語記事投稿を確実に動かす
```bash
cd /Users/sakonhiroki/note-post-mcp
# 動作確認済みのバージョンをチェックアウト（タグがあれば）
```

---

**このファイルを保存しておけば、Cursor再起動時に混乱することはありません！**

