# note 投稿（HTTP API・ブラウザ不要）

Playwright でログインできない／「Could not log you in」になる場合の **別ルート**です。

note は**公式の公開 API を出していません**が、ブラウザが使っている **内部 API**（`POST /api/v1/text_notes` 等）に、**ログイン済みの Cookie だけ**を付けてリクエストします。  
GitHub Actions 上で **ブラウザを一切起動しません**（ログイン画面を通らない）。

---

## 仕組み

| 従来（Playwright） | HTTP API モード |
|-------------------|-----------------|
| CI でブラウザが note にログインしようとする | **ログイン処理なし** |
| ボット判定で弾かれやすい | **Cookie が有効なら**サーバーは通常の利用と同等に見える |

Cookie の取得は **スクリプトがブラウザを開き、自動で1行ファイルに保存**します。DevTools でヘッダをコピーする必要はありません。

---

## セットアップ

### 1. Secret: `NOTE_SESSION_COOKIE`（必須・これだけで HTTP API が使われる）

**`NOTE_EMAIL` / `NOTE_PASSWORD` / `NOTE_AUTH_STATE` だけでは HTTP API には切り替わりません。**  
別名として **`NOTE_SESSION_COOKIE`** という名前の Secret を **1つ新規追加**してください（一覧に無ければ未設定です）。

手元の Mac でターミナル:

```bash
cd /path/to/hongkong-daily-news-note
npm install
npm run note:cookie
```

1. **スクリプトが Chrome を開く**（あなたが DevTools を触る必要はない）  
2. 開いたウィンドウで **note にログイン**（二段階もここで）  
3. できれば **エディタの新規記事**まで開く  
4. ターミナルに戻り **Enter**  
5. プロジェクト直下に **`.note-session-cookie.txt`** ができる → **中身をすべてコピー**  
6. GitHub → **Secrets** → **`NOTE_SESSION_COOKIE`** に貼り付け（保存）

**注意:** Cookie はセッションと同等です。漏洩するとアカウントを操作される可能性があります。

**うまくいかないとき**（ログイン画面で弾かれる等）だけ、最終手段として **手動で Chrome にログインし、DevTools の Request Headers の Cookie 行をコピー**する方法もあります。

`NOTE_SESSION_COOKIE` が **1文字でも入っていれば**、Actions は **自動で HTTP API** を使います（以前の「Variables に `USE_NOTE_API=true`」は**不要**）。

### 2. （任意）Variable `USE_NOTE_API`

- **通常は不要**です。
- `USE_NOTE_API=true` にしたのに **`NOTE_SESSION_COOKIE` を入れ忘れた**ときだけ、ワークフローを失敗させて気づけるようにしています。

### 3. プッシュ

`main` にマージ後、Secret に Cookie があれば **HTTP API** で `post_to_note_api.js` が実行されます。

---

## 非公式 API のための注意

- **仕様変更で突然動かなくなる**可能性があります  
- **利用規約・禁止事項**は自己責任で確認してください（自動投稿の可否は note の規約に依存）  
- **マガジン自動追加**はこのスクリプトでは未実装の場合があります（必要なら手動でマガジンに追加）  
- **見出し画像**は API 経由のアップロード仕様が未整備のため、本文中のローカル画像はプレースホルダに置き換わる場合があります

---

## ローカルで試す

```bash
cd /path/to/hongkong-daily-news-note
npm install
NOTE_SESSION_COOKIE='（コピーしたCookie行）' node post_to_note_api.js daily-articles/hongkong-news_2026-01-01.md 公開
```

---

## Cookie が切れたら

再ログインして **Cookie を取り直し**、`NOTE_SESSION_COOKIE` を更新してください。

## 元に戻す（Playwright）

Secret **`NOTE_SESSION_COOKIE` を削除**（または空にできない場合は名前を変える）すると、従来どおり Playwright 投稿になります。
