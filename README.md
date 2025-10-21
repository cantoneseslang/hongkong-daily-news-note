# 🇭🇰 香港デイリーニュース自動生成システム

毎日香港のニュースを自動取得し、Grok AIで日本語記事を生成するシステムです。

**⚠️ 注意**: このプロジェクトは`note-post-mcp`とは**完全に独立**しています。結合しないでください。

## 📋 システム概要

```
┌─────────────────────────────────────────┐
│  1. ニュース取得（並列実行）            │
│  ├─ News API (country=hk)              │
│  ├─ World News API (source-country=hk) │
│  └─ NewsData API (country=HK)          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  2. Grok API (grok-2-latest)            │
│  - 重複除去・フィルタリング             │
│  - 日本語要約生成                       │
│  - Markdown記事生成                     │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  3. note投稿（手動）                    │
│  - Cursor MCP経由、または               │
│  - 手動コピー＆ペースト                 │
└─────────────────────────────────────────┘
```

## 🚀 セットアップ

### 1. 依存パッケージのインストール

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
pip install -r requirements.txt
```

### 2. 設定ファイルの確認

`config.json`に以下の情報が設定されています：

- **APIキー**
  - NewsData.io
  - World News API
  - News API
  - xAI Grok API

- **スケジュール設定**
  - 実行時刻: 毎日 08:00 (JST)
  - タイムゾーン: Asia/Tokyo

## 📖 使い方

### 手動実行（各ステップ）

#### ステップ1: ニュース取得
```bash
python fetch_hongkong_news.py
```
→ `daily-articles/raw_news_YYYY-MM-DD_HH-MM-SS.json` に保存

#### ステップ2: 記事生成（Grok API）
```bash
python generate_article.py daily-articles/raw_news_YYYY-MM-DD_HH-MM-SS.json
```
→ `daily-articles/hongkong-news_YYYY-MM-DD.md` に保存

#### ステップ3: note投稿準備
```bash
python post_to_note.py daily-articles/hongkong-news_YYYY-MM-DD.md
```
→ 投稿方法の案内を表示（詳細は`manual_post_to_note.md`参照）

### 自動実行（スケジューラー）

```bash
python scheduler.py
```

- **初回起動時**: すぐにテスト実行
- **その後**: 毎日 08:00 に自動実行
- **停止**: `Ctrl+C`

## 📁 ディレクトリ構成

```
hongkong-daily-news-note/
├── config.json                 # API設定・スケジュール設定
├── fetch_hongkong_news.py      # ニュース取得スクリプト
├── generate_article.py         # Grok記事生成スクリプト
├── post_to_note.py            # note投稿スクリプト
├── scheduler.py               # 自動実行スケジューラー
├── requirements.txt           # 依存パッケージ
├── README.md                  # このファイル
└── daily-articles/            # 生成ファイル保存先
    ├── raw_news_*.json        # 取得した生ニュース
    └── hongkong-news_*.md     # 生成した記事
```

## 🔧 カスタマイズ

### スケジュール時刻の変更
`config.json`の`schedule_time`を編集：
```json
{
  "settings": {
    "schedule_time": "08:00"  // 例: "20:00"に変更
  }
}
```

### 取得ニュース数の変更
`config.json`の`news_count`を編集：
```json
{
  "settings": {
    "news_count": 10  // 例: 20に変更
  }
}
```

### Grokモデルの変更
`generate_article.py`の`model`パラメータを編集：
```python
"model": "grok-beta"  # または "grok-4-latest"
```

## 🔐 セキュリティ

- `config.json`にAPIキーが含まれています
- **Gitにコミットしないでください**
- 必要に応じて`.gitignore`に追加してください

## 🐛 トラブルシューティング

### API制限エラー
- 各APIには無料プランの制限があります
- 制限を超えた場合は翌日まで待つか、有料プランにアップグレード

### Grok APIエラー
- APIキーが正しいか確認
- モデル名が正しいか確認（`grok-beta` または `grok-4-latest`）

### note投稿エラー
- `.note-state.json`が存在するか確認
- note MCPツールが正しく設定されているか確認

## 📊 API情報

| API | 無料プラン | 制限 |
|-----|-----------|------|
| NewsData.io | ✅ | 1日200リクエスト |
| World News API | ✅ | 1日1,000リクエスト |
| News API | ✅ | 1日100リクエスト |
| xAI Grok | ✅ | クレジット制 |

## 📝 ログ

すべての実行ログは標準出力に表示されます。
ログファイルに保存したい場合：

```bash
python scheduler.py >> logs/scheduler.log 2>&1
```

## 🔄 更新履歴

- **2025-10-16**: 初回リリース
  - 3つのニュースAPI統合
  - Grok API連携
  - note MCP自動投稿
  - スケジューラー実装

## 📞 サポート

問題が発生した場合は、各スクリプトを個別に実行してエラーメッセージを確認してください。

---

## ⚠️ 重要な注意事項

### プロジェクトの独立性

このプロジェクト（`hongkong-daily-news-note`）は、`note-post-mcp`プロジェクトとは**完全に独立**しています。

- ✅ **独立したAPI**: 3つのニュースAPI + Grok API
- ✅ **独立した記事生成**: Grok AIによる日本語記事生成
- ✅ **独立した設定**: `config.json`で完結
- ✅ **独立したスケジューラー**: 毎日自動実行

**絶対に結合しないでください！** 両プロジェクトは別々の目的で使用されます。

### note投稿について

note投稿は以下の方法で行います：
1. **Cursor MCP経由**（推奨）
2. **手動コピー＆ペースト**

詳細は `manual_post_to_note.md` を参照してください。

---

**開発者**: Sako Hiroki  
**プロジェクト**: hongkong-daily-news-note  
**最終更新**: 2025-10-16

