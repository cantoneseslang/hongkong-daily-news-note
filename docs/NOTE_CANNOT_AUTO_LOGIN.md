# note に「そもそも入れない」／自動投稿が通らないとき

## まず試す: HTTP API で投稿（ブラウザログインなし）

Playwright で **ログイン画面に入れない**場合でも、**普段のブラウザで取得した Cookie** だけを GitHub Secret に入れ、**CI ではブラウザを使わず** note の内部 API に投稿する方法があります。  
手元でブラウザにログインするときは **メールで通らなくても、X（𝕏）や Google などソーシャルログインでかまいません**（`note_session` が Cookie に入ればよい）。

→ **[NOTE_API_POST.md](./NOTE_API_POST.md)**（`USE_NOTE_API=true` と `NOTE_SESSION_COOKIE`）

---

## 結論（ブラウザ自動操作の話）

**note.com は、自動操作・データセンター IP・未知の環境からのログインを強く制限します。**  
Playwright だけでは**根本的に通らない**ことがあります。  
それは**あなたの設定ミスだけではなく、サービス側のポリシー**です。

次のどれかに当てはまると、**ローカルでも GitHub Actions でもログインできない**ことがあります。

- ブラウザが「自動操作」扱いになる（Playwright / Chromium / CI）
- IP がクラウド・VPN などで信頼されにくい
- 短時間に連続で試して一時ブロック
- アカウント側の保護（CAPTCHA・追加認証）

---

## コードでは解決できないこと

- note の「Could not log you in now」を **100% 回避する**保証はない
- **公式の「自動投稿用 API」**（個人向けの安定したもの）はない

---

## 現実的な運用

### A. 記事だけ自動（おすすめの落とし所）

GitHub Actions で **毎日 `daily-articles/hongkong-news_YYYY-MM-DD.md` を生成・コミット**するまでにして、**note への貼り付けは手動**にする。

- リポジトリの `main` からその日の `.md` を開く
- ブラウザで **普段使いの Chrome** から note にログインし、**コピペで公開**

### B. Actions で自動投稿をやめる（設定1つ）

リポジトリで **Variables** を設定すると、CI から **note 投稿ステップをスキップ**できます。

1. GitHub → **Settings** → **Secrets and variables** → **Actions** → **Variables** タブ  
2. **New repository variable**  
   - Name: `SKIP_NOTE_POST`  
   - Value: `true`  

→ 記事生成・Git push は続き、**Playwright で note を開く処理は走りません**。

（戻すときは `SKIP_NOTE_POST` を削除するか、`false` に変更）

### C. 別アカウントで試す（任意）

**二段階認証なし**の専用アカウントだけを自動投稿に使う、など。  
それでも **弾かれる**場合は A か B に寄せるしかありません。

---

## まとめ

| 症状 | 意味 |
|------|------|
| 普通の Chrome では入れる | 自動操作では入れないだけ |
| どうやっても入れない | その環境では note が許可しない |

**「そもそも入れない」なら、自動投稿に固執せず、生成は Git に任せて note は手動**が一番確実です。
