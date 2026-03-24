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

手元の Mac でターミナル（**1行ずつ** Enter で実行）:

```bash
cd /path/to/hongkong-daily-news-note
npm install
npx playwright install chromium
npm run note:cookie
```

1. **スクリプトがブラウザを開く**（既定は **Playwright 同梱 Chromium**＋**永続プロファイル**。Chrome が落ちる場合に向いています）  
2. 開いたウィンドウで **note にログイン**  
   - **メール＋パスワードで通らない**場合は、**X（𝕏）・Google などのソーシャルログイン**で問題ありません（Cookie に `note_session` が入ればよい）。  
   - 二段階認証がある場合はその画面で完了。  
3. できれば **エディタの新規記事**まで開く  
4. ターミナルに戻り **Enter**  
5. プロジェクト直下に **`.note-session-cookie.txt`** ができる → **中身をすべてコピー**  
6. GitHub → **Secrets** → **`NOTE_SESSION_COOKIE`** に貼り付け（保存）

**環境変数（任意）**

| 変数 | 意味 |
|------|------|
| `NOTE_COOKIE_USE_GOOGLE_CHROME=1` | 最初から **Google Chrome** で開く（同梱 Chromium より先） |
| `NOTE_COOKIE_NON_PERSISTENT=1` | 永続プロファイルを使わず、従来どおり一時プロファイル |
| `NOTE_COOKIE_PROFILE_DIR=パス` | プロファイル保存先を変更 |

**注意:** Cookie はセッションと同等です。漏洩するとアカウントを操作される可能性があります。

**うまくいかないとき**（「入れない」／ログイン画面で弾かれる／Chrome がクラッシュする）

- **Google Chrome で試す:** `NOTE_COOKIE_USE_GOOGLE_CHROME=1 npm run note:cookie`
- **同梱 Chromium を入れ直す:** `npx playwright install chromium`
- **「普通の Chrome」のログインをそのまま使いたい:** `npm run note:cookie:cdp`  
  （**いま開いている Chrome に後から勝手に接続はできない**ため、Chrome を一度終了し、スクリプトに書いてある **リモートデバッグ付き**で起動し直したうえで接続します。理由はスクリプト先頭の説明を参照。）
- **最終手段:** DevTools → Application → Cookies で `note_session` をコピー

`NOTE_SESSION_COOKIE` が **1文字でも入っていれば**、Actions は **自動で HTTP API** を使います（以前の「Variables に `USE_NOTE_API=true`」は**不要**）。

### 2. （任意）Variable `USE_NOTE_API`

- **通常は不要**です。
- `USE_NOTE_API=true` にしたのに **`NOTE_SESSION_COOKIE` を入れ忘れた**ときだけ、ワークフローを失敗させて気づけるようにしています。

### 3. プッシュ

`main` にマージ後、Secret に Cookie があれば **HTTP API** で `post_to_note_api.js` が実行されます。

---

## 422 Unprocessable Entity になっていた理由（参考）

note の投稿は **1回の `POST` に `status: published` を付ける形式ではなく**、多くの場合 **`POST /api/v1/text_notes`（`name` と `body` のみ）→ `POST .../draft_save?id=...`** の **2段階**です。前者だけだと 422 になりやすいです。`post_to_note_api.js` はこの流れに合わせています。

**422 が続くときの追加オプション**

- スクリプトは **まず生の Cookie で `create`** を試し、失敗したときだけ **ウォームアップ GET**（`Set-Cookie` のマージ）のあと再試行します。ウォームアップがセッションを壊すケースがあるため、**Repository Variables** に **`NOTE_API_SKIP_WARMUP=true`**（または `1`）を入れると **ウォームアップを完全にスキップ**し、Secret の Cookie のみで投稿します（`.github/workflows/daily-news.yml` がこの変数を環境に渡します）。
- 併せて **`Origin` / `Referer` の複数パターン**や **`application/x-www-form-urlencoded`** でも `create` を試します（ブラウザに近いヘッダ差分の吸収）。

## CloudFront 403（「cachable requests only」）になる場合

**GitHub Actions のランナー（データセンター IP）から note の API へ POST すると、CloudFront/WAF でブロックされる**ことがあります。Cookie が正しくても再現します。  
`post_to_note_api.js` は **`https://note.com/api/...` のみ**に POST し、`editor.note.com` への POST は行いません（別 CDN で 403 になりやすいため）。

**対処の例**

- **Variables** に `SKIP_NOTE_POST=true` → 記事生成とコミットだけ行い、note 投稿は手動
- **手元の Mac** で `NOTE_SESSION_COOKIE=... node post_to_note_api.js ...` が通るか確認（通れば IP 制限の可能性大）
- **セルフホストランナー**（自宅 PC 等）でワークフローを動かす

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
