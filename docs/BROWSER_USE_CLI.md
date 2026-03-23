# Browser Use CLI（ターミナルから実ブラウザ）

[Browser Use CLI](https://docs.browser-use.com) は、ターミナルから **実ブラウザ** を操作するツールです。ログイン状態や Cookie を扱いやすく、AI エージェント連携も想定された仕組みです。

このリポジトリの **GitHub Actions → note 投稿** で使う `NOTE_AUTH_STATE` は、**Playwright の `storageState` JSON**（`cookies` + `origins`）である必要があります。

---

## 1. インストール（公式ワンライナー）

```bash
curl -fsSL https://browser-use.com/cli/install.sh | bash
```

- 終了後、**ターミナルを開き直す**か `source ~/.zshrc`（bash なら `~/.bashrc`）で PATH を反映。
- 初回は `uv` や仮想環境 `~/.browser-use-env` が使われます。

詳細: [Browser Use ドキュメント](https://docs.browser-use.com)

---

## 2. 基本コマンド例（note まで）

```bash
browser-use open https://note.com/login
# または
browser-use open https://editor.note.com/new
```

- ブラウザが開いたら **手動でログイン**（二段階認証も可）。
- 要素一覧: `browser-use state`
- クリック: `browser-use click <インデックス>`
- 終了: `browser-use close`（ヘルプやドキュメントに従う）

---

## 3. GitHub Secret `NOTE_AUTH_STATE` 用の JSON を作る

Browser Use で「ログインできた」だけでは、**このリポジトリの `note_auto_post.js` が読む JSON** と形式が一致するとは限りません。  
**Playwright がそのまま保存する `storageState`** が一番確実です。

### note が「Could not log you in」と出るとき（推奨）

Playwright が起動した Chrome は**手動の Chrome と区別**され、ログインできないことがあります。次を使ってください。

```bash
cd /path/to/hongkong-daily-news-note
npm run note:auth:cdp
```

手順は **[NOTE_AUTH_STATE_LOCAL.md](./NOTE_AUTH_STATE_LOCAL.md)** の「手動 Chrome + CDP」参照。

---

### 代替: Playwright `open` で終了時に保存（環境によっては弾かれる）

```bash
cd /path/to/hongkong-daily-news-note
npx playwright open https://editor.note.com/new --channel=chrome --save-storage=.note-auth-state.json
```

1. 開いた **Google Chrome** で note にログインし、エディタが表示されるまで進める。  
2. **ブラウザを閉じる**と、終了時に `.note-auth-state.json` が書き出されます。

1 行にまとめて Secret に貼りやすくする例:

```bash
node -e "const fs=require('fs'); const j=JSON.parse(fs.readFileSync('.note-auth-state.json','utf8')); console.log(JSON.stringify(j));" > .note-auth-state.compact.json
```

→ `.note-auth-state.compact.json` の中身を GitHub **Settings → Secrets → `NOTE_AUTH_STATE`** に貼り付け。

npm スクリプトでも同じことができます:

```bash
npm run note:auth:storage
```

（`package.json` の `note:auth:storage` を参照）

### 代替: このリポジトリの対話スクリプト

```bash
npm run note:auth
```

→ Google Chrome 優先で開き、Enter 後に `.note-auth-state.json` / `.note-auth-state.compact.json` を出力。

---

## 4. Browser Use と併用するイメージ

| 用途 | 向いているもの |
|------|----------------|
| ターミナルからブラウザを開く・要素を確認する | **Browser Use CLI** |
| Cursor / Claude Code と AI エージェントで操作する | **Browser Use**（[ドキュメント](https://docs.browser-use.com)） |
| **このリポジトリの `NOTE_AUTH_STATE` を更新する** | **Playwright `open --save-storage`** または **`npm run note:auth`** |

---

## 5. 注意

- `NOTE_AUTH_STATE` は**秘密情報**です。リポジトリにコミットしないでください（`.gitignore` に含めています）。
- Browser Use の **Profile Sync**（`profile.sh` 等）はクラウド連携向けです。GitHub Actions の note 投稿だけなら、上記の **Playwright 形式 JSON** で足りることが多いです。
