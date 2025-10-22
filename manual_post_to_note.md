# 📮 note投稿マニュアル

生成された記事をnoteに投稿する方法です。

## 方法1: Cursor MCP経由（推奨）

CursorのMCPツールを使用して投稿します。

### 手順

1. Cursorで以下のコマンドを実行：

```
mcp_note-post-mcp_save_draft
```

2. パラメータを入力：
   - `markdown_path`: 生成された記事のパス（例: `/Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_2025-10-16.md`）
   - `state_path`: `/Users/sakonhiroki/.note-state.json`
   - `timeout`: `180000`

## 方法2: 手動コピー＆ペースト

1. 生成された`.md`ファイルを開く
2. 内容をコピー
3. https://note.com/creator にアクセス
4. 新規記事作成
5. タイトルと本文を貼り付け
6. タグを設定
7. 下書き保存または公開

## 方法3: note-post-mcpプロジェクトを使用（非推奨）

**注意**: `note-post-mcp`プロジェクトとは完全に独立しているため、使用する場合は別途そちらのプロジェクトで実行してください。

```bash
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js /Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_YYYY-MM-DD.md
```

---

**推奨**: 方法1（Cursor MCP）が最もスムーズです。

