# ローカルで NOTE_AUTH_STATE を更新する

GitHub Actions の `NOTE_AUTH_STATE`（note のログイン状態）が古い／無効なとき、手元のブラウザで一度ログインしてから JSON を作り直します。

**どうしてもログインできない／自動投稿を諦める場合**は **[NOTE_CANNOT_AUTO_LOGIN.md](./NOTE_CANNOT_AUTO_LOGIN.md)** を参照（手動投稿・`SKIP_NOTE_POST` で投稿スキップ）。

## Browser Use CLI を使う場合

ターミナルから実ブラウザを操作する **Browser Use CLI** と、このリポジトリで必要な **Playwright 形式の JSON** の関係は、**[BROWSER_USE_CLI.md](./BROWSER_USE_CLI.md)** にまとめています。

- インストール例: `curl -fsSL https://browser-use.com/cli/install.sh | bash`
- **Secret 用ファイル**は `npx playwright open ... --save-storage` または `npm run note:auth` が確実です。

## 普通の Chrome では入れるのに、Playwright / `playwright open` だけ弾かれる

**手で開いた Chrome** と、**Playwright が起動した Chrome** は別扱いになり、note が **「Could not log you in now」** と出すことがあります（自動操作検出）。

### いちばん確実: 手動 Chrome + CDP で state を保存（推奨）

Playwright にブラウザを起動させず、**自分でリモートデバッグ付き Chrome を起動 → 手動ログイン → スクリプトが Cookie を書き出す**方法です。

```bash
cd /path/to/hongkong-daily-news-note
npm install
npm run note:auth:cdp
```

事前に別ターミナルで Chrome を起動するコマンドは、実行時に表示されます（`--remote-debugging-port=9222` と専用 `--user-data-dir`）。

---

## 補足: `npm run note:auth`（Playwright が Chrome を起動）

`npm run note:auth` は **Google Chrome 優先 + 検出されにくい起動オプション**を付けていますが、**note 側の仕様次第では同じエラーになる**ことがあります。そのときは上の **`note:auth:cdp`** を使ってください。

## 手順

1. **依存関係**

   ```bash
   cd /path/to/hongkong-daily-news-note
   npm install
   ```

   Google Chrome が入っていれば、追加で `playwright install chromium` は不要です（Chrome 起動を試すため）。

2. **スクリプト実行**

   ```bash
   npm run note:auth
   ```

   または

   ```bash
   node scripts/note_save_auth_state.js
   ```

3. ブラウザが開くので **note にログイン**（二段階認証も可）。  
   可能なら **新規記事エディタ**（`https://editor.note.com/new`）まで進める。

4. ターミナルに戻り、指示どおり **Enter** を押す。

5. リポジトリ直下に次ができます（デフォルト）:

   - `.note-auth-state.json` … 整形済み
   - `.note-auth-state.compact.json` … **1行（Secret 用におすすめ）**

6. **GitHub**  
   リポジトリ → **Settings** → **Secrets and variables** → **Actions** → `NOTE_AUTH_STATE` を編集し、  
   **`.note-auth-state.compact.json` の中身をすべてコピーして貼り付け**（保存）。

7. `.gitignore` に `.note-auth-state*.json` を追加してコミットしないようにすると安全です。

## 注意

- この JSON は**ログイン情報に相当する**ので、**公開リポジトリに push しない**でください。
- Secret のサイズ制限に引っかかる場合は、1行版（compact）を使ってください。
- どうしても同梱 Chromium のみで試したい場合: `NOTE_AUTH_FORCE_CHROMIUM=1 npm run note:auth`
