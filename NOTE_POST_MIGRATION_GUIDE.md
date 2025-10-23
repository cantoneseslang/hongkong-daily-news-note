# 📦 note.com自動投稿機能 移植ガイド

このプロジェクトで実装されているnote.com自動投稿機能を、他のプロジェクトに移植するための完全ガイドです。

---

## 🎯 移植する機能

1. ✅ note.comへの自動ログイン
2. ✅ 認証状態の保存・再利用
3. ✅ Markdownからの記事投稿
4. ✅ 目次の自動挿入
5. ✅ headlessモード対応（GitHub Actions）
6. ✅ 画像アップロード対応（オプション）

---

## 📋 移植チェックリスト

### 準備
- [ ] `note_auto_post.js` をコピー
- [ ] `package.json` に playwright 追加
- [ ] `npx playwright install chromium` 実行

### ローカルテスト
- [ ] Markdownファイルの準備（形式確認）
- [ ] 初回ログインテスト
- [ ] 認証状態ファイル（`~/.note-state.json`）の確認
- [ ] 2回目以降の投稿テスト（認証状態再利用）

### GitHub Actions（必要な場合）
- [ ] `NOTE_AUTH_STATE` をSecretsに追加
- [ ] Chromiumオプションの確認
- [ ] ワークフローの設定
- [ ] CI環境でのテスト実行

---

## 1️⃣ 必要なファイル

### メインファイル
```
note_auto_post.js  → 移植先プロジェクトにコピー
```

### 依存関係

#### package.json
```json
{
  "dependencies": {
    "playwright": "^1.40.0"
  }
}
```

#### インストール
```bash
npm install playwright
npx playwright install chromium
```

---

## 2️⃣ 使用方法

### 基本的な呼び出し

```bash
node note_auto_post.js <記事ファイル.md> <ユーザー名> <パスワード> [認証状態ファイルのパス]
```

### パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| 記事ファイル | ✅ | Markdownファイルのパス | `article.md` |
| ユーザー名 | ✅ | note.comのユーザー名/メール | `bestinksalesman` |
| パスワード | ✅ | note.comのパスワード | `password123` |
| 認証状態ファイル | ⬜ | 認証状態ファイルのパス | `~/.note-state.json` |

### 実行例

#### 初回実行（ログインが必要）
```bash
node note_auto_post.js daily-news.md myusername mypassword
```

#### 2回目以降（認証状態を再利用）
```bash
node note_auto_post.js daily-news.md myusername mypassword ~/.note-state.json
```

---

## 3️⃣ Markdownファイルの形式

### 基本構造

```markdown
# タイトル

（空行 - ここに目次が自動挿入される）

## セクション1

本文本文本文...

## セクション2

本文本文本文...

---
**タグ**: タグ1,タグ2,タグ3
```

### 重要なポイント

1. **タイトルの直後に空行を1つ入れる**
   - この空行の位置に目次が自動挿入されます

2. **見出しは `##` または `###` を使用**
   - note.comの目次機能は見出しから自動生成されます

3. **最後のセクション（オプション）**
   ```markdown
   ---
   **タグ**: タグ1,タグ2,タグ3
   **生成日時**: 2025年10月23日 15:00
   ```

---

## 4️⃣ 認証状態の管理

### ローカル開発

#### 認証状態ファイルの場所
```
~/.note-state.json
```

#### 初回ログイン
```bash
# 初回実行時、ブラウザが開いてログインページに移動
# 自動ログインが試みられ、成功すると認証状態が保存される
node note_auto_post.js article.md username password
```

#### 2回目以降
```bash
# 認証状態ファイルが自動的に使用される
node note_auto_post.js article.md username password
```

### GitHub Actions

#### 認証状態の取得
```bash
# ローカルでログイン後、認証状態を取得
cat ~/.note-state.json | python3 -c "import json, sys; print(json.dumps(json.load(sys.stdin)))"
```

#### GitHub Secretsへの保存
1. https://github.com/ユーザー名/リポジトリ名/settings/secrets/actions
2. 「New repository secret」をクリック
3. Name: `NOTE_AUTH_STATE`
4. Secret: 上記で取得したJSON文字列（2833文字）

**重要**: 
- Base64エンコード不要、JSON文字列をそのまま保存
- サイズ: 2833文字（正常）、1005文字（不完全）

#### ワークフローでの使用

```yaml
- name: Post to note.com
  env:
    NOTE_EMAIL: ${{ secrets.NOTE_EMAIL }}
    NOTE_PASSWORD: ${{ secrets.NOTE_PASSWORD }}
    NOTE_AUTH_STATE: ${{ secrets.NOTE_AUTH_STATE }}
  run: |
    # 認証状態ファイルを作成
    if [ -n "$NOTE_AUTH_STATE" ]; then
      echo "$NOTE_AUTH_STATE" > /tmp/.note-state.json
    fi
    
    # note.com投稿を実行
    node note_auto_post.js \
      "$LATEST_ARTICLE" \
      "$NOTE_EMAIL" \
      "$NOTE_PASSWORD" \
      /tmp/.note-state.json
```

---

## 5️⃣ GitHub Actions設定（CI/CD環境）

### 必須の環境変数

```yaml
env:
  CI: true  # Playwrightのheadlessモード判定に使用
  NOTE_EMAIL: ${{ secrets.NOTE_EMAIL }}
  NOTE_PASSWORD: ${{ secrets.NOTE_PASSWORD }}
  NOTE_AUTH_STATE: ${{ secrets.NOTE_AUTH_STATE }}
```

### Playwrightのインストール

```yaml
- name: Setup Playwright
  run: |
    npm install
    npx playwright install chromium
```

### 完全なワークフロー例

```yaml
name: Post to note.com

on:
  push:
    branches: [main]

jobs:
  post:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: |
          npm install
          npx playwright install chromium
      
      - name: Post to note.com
        env:
          NOTE_EMAIL: ${{ secrets.NOTE_EMAIL }}
          NOTE_PASSWORD: ${{ secrets.NOTE_PASSWORD }}
          NOTE_AUTH_STATE: ${{ secrets.NOTE_AUTH_STATE }}
        run: |
          # 認証状態ファイルを作成
          if [ -n "$NOTE_AUTH_STATE" ]; then
            echo "$NOTE_AUTH_STATE" > /tmp/.note-state.json
          fi
          
          # 最新の記事ファイルを取得
          LATEST_ARTICLE=$(ls -t articles/*.md | head -1)
          
          # note.com投稿を実行
          node note_auto_post.js \
            "$LATEST_ARTICLE" \
            "$NOTE_EMAIL" \
            "$NOTE_PASSWORD" \
            /tmp/.note-state.json
```

---

## 6️⃣ 重要なコード設定

### Chromiumオプション（GitHub Actions対応）

```javascript
// note_auto_post.js (170-181行目)

// GitHub Actions環境ではheadless: true、ローカルではheadless: false
const isCI = process.env.CI === 'true';

const browser = await chromium.launch({
  headless: isCI,  // CIではtrue
  args: [
    '--lang=ja-JP',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',  // ← CI必須
    '--disable-gpu'              // ← CI必須
  ],
});
```

**重要ポイント**:
- `--disable-dev-shm-usage`: GitHub Actionsで必須（共有メモリ問題を回避）
- `--disable-gpu`: GPU無効化（headless環境で安定）
- `--no-sandbox`, `--disable-setuid-sandbox`: セキュリティ制約の回避

### Context設定（Viewport & User-Agent）

```javascript
// note_auto_post.js (185-189行目)

let contextOptions = {
  locale: 'ja-JP',
  viewport: { width: 1280, height: 800 },  // ← 必須
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',  // ← 必須
};

if (existsSync(statePath)) {
  contextOptions.storageState = statePath;
}

const context = await browser.newContext(contextOptions);
```

### ページロード待機

```javascript
// note_auto_post.js (194-196行目)

// networkidle を使用（全リソース読み込み完了まで待機）
await page.goto('https://editor.note.com/new', { 
  waitUntil: 'networkidle',  // ← 重要
  timeout: 30000 
});
await page.waitForTimeout(3000);  // ← 安定化のための追加待機
```

**変更前（失敗）**:
```javascript
await page.goto('...', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2000);
```

### タイムアウト延長

```javascript
// note_auto_post.js (248-251行目)

// タイトル入力欄の待機タイムアウトを延長
await page.waitForSelector('textarea[placeholder*="タイトル"]', { 
  timeout: 30000  // 10秒 → 30秒
});
```

---

## 7️⃣ 目次自動挿入の実装

### コード全体

```javascript
// note_auto_post.js (355-398行目)

const lines = body.split('\n');
let tocInsertLine = -1;
let shouldInsertToc = false;

// 1. 目次挿入位置の検出（一番最初の空行）
for (let i = 0; i < lines.length; i++) {
  if (lines[i].trim() === '') {
    tocInsertLine = i;
    shouldInsertToc = true;
    console.log(`✓ 目次挿入位置を${i}行目で検出（一番最初の空行）`);
    break;
  }
}

// 2. 目次挿入（本文入力前）
if (shouldInsertToc && tocInsertLine === 0) {
  console.log('📋 目次を挿入中（本文入力前）...');
  
  try {
    // +ボタンをクリック（メニューを開く）
    const menuButton = page.locator('button[aria-label="メニューを開く"]');
    await menuButton.waitFor({ state: 'visible', timeout: 5000 });
    await menuButton.click();
    await page.waitForTimeout(1000);
    console.log('✓ メニューを開きました');
    
    // 目次ボタンをクリック
    const tocButton = page.locator('button:has-text("目次")');
    await tocButton.waitFor({ state: 'visible', timeout: 5000 });
    await tocButton.click();
    await page.waitForTimeout(3000);
    console.log('✓ 目次を挿入しました');
    
    // 目次の後に改行して、次の行に移動
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    
    shouldInsertToc = false; // 挿入済みフラグ
  } catch (e) {
    console.log('⚠️  目次挿入エラー:', e.message);
    console.log('手動で目次を挿入してください。');
  }
}

// 3. 本文入力時、最初の空行をスキップ
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  
  // 目次を挿入した場合、最初の空行はスキップ
  if (i === 0 && tocInsertLine === 0 && !shouldInsertToc) {
    continue;
  }
  
  // 以降、通常の本文入力処理...
}
```

### 動作フロー

1. **タイトル入力完了後**、カーソルは本文の最初の行（空行）にある
2. **+ボタン（メニューを開く）** をクリック
3. **目次ボタン** をクリック
4. 目次ブロックが挿入される
5. **Enter** で次の行に移動
6. 本文入力開始（最初の空行はスキップ）

### note.comの目次機能

- 記事内の `##` や `###` 見出しから自動生成
- 目次ブロックを挿入するだけで、内容は自動更新される
- クリック可能なリンク付き目次になる

---

## 8️⃣ トラブルシューティング

### 1. 認証状態のサイズ確認

```bash
# GitHub Actionsログで確認
📄 認証状態ファイルサイズ: 2833 bytes  # ✅ 正常
📄 認証状態ファイルサイズ: 1005 bytes  # ❌ 不完全
```

**対処法**:
- 2833文字でない場合、GitHub Secretsの`NOTE_AUTH_STATE`を再設定
- JSON文字列全体をコピー&ペーストすること

### 2. headlessモードでタイムアウト

**症状**:
```
❌ エラー発生: page.waitForSelector: Timeout 10000ms exceeded.
Call log:
  - waiting for locator('textarea[placeholder*="タイトル"]') to be visible
```

**原因**:
- Chromiumオプションが不足
- ページロード待機が不十分

**対処法**:
```javascript
// Chromiumオプションを確認
args: [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',  // ← 必須
  '--disable-gpu'              // ← 必須
]

// ページロード待機を変更
await page.goto('...', { 
  waitUntil: 'networkidle',  // ← 必須
  timeout: 30000 
});
await page.waitForTimeout(3000);  // ← 安定化
```

### 3. 本文入力が止まる

**症状**:
```
📝 本文入力中...
（処理が止まる）
```

**原因**:
- headlessモードで本文入力が遅い（正常動作）
- 12,000文字の場合、5-10分かかる

**対処法**:
- 進捗ログを追加（10行ごと）
```javascript
if (i > 0 && i % 10 === 0) {
  console.log(`  進捗: ${i}/${lines.length}行 (${Math.round(i/lines.length*100)}%)`);
}
```

### 4. 目次が挿入されない

**症状**:
- 目次ブロックが表示されない

**原因**:
- Markdownファイルの形式が正しくない
- タイトル直後の空行がない

**対処法**:
```markdown
# タイトル
         ← この空行が必須！
## セクション1
```

---

## 9️⃣ 参考ファイル

### このプロジェクト内の重要ファイル

| ファイル | 参照箇所 | 説明 |
|---------|---------|------|
| `note_auto_post.js` | 全体 | メインスクリプト |
| `.github/workflows/daily-news.yml` | 175-215行目 | GitHub Actions設定 |
| `RESTORE_POINT.md` | 231-313行目 | 2025-10-23 修正内容 |

### 重要なコード箇所（note_auto_post.js）

| 行番号 | 内容 |
|--------|------|
| 170-181 | Chromium起動設定 |
| 185-189 | Context設定（viewport, userAgent） |
| 194-246 | ページロードと認証確認 |
| 248-251 | タイトル入力 |
| 355-398 | 目次挿入 |
| 400-650 | 本文入力 |

### 参考になる他のファイル

| ファイル | 説明 |
|---------|------|
| `post_to_note_github_actions.js` | GitHub Actions用の設定が記載 |
| `post_to_note_playwright.js` | Playwrightの基本実装 |

---

## 🔟 よくある質問（FAQ）

### Q1: ローカルでは動くのにGitHub Actionsで失敗する

**A**: Chromiumオプションとページロード待機を確認
```javascript
// 必須オプション
args: [
  '--disable-dev-shm-usage',
  '--disable-gpu'
]

// 必須待機設定
waitUntil: 'networkidle'
```

### Q2: 認証状態が復元されない

**A**: サイズを確認（2833文字が正常）
```bash
# ログで確認
📄 認証状態ファイルサイズ: 2833 bytes
```

### Q3: 目次が空になる

**A**: note.comの目次機能は見出し（`##`, `###`）から自動生成されます
- 記事内に見出しがあることを確認
- 目次ブロック挿入後、自動的に内容が生成される

### Q4: 本文入力が遅い

**A**: 正常動作です
- headlessモードでは1行ずつ入力するため時間がかかる
- 12,000文字で約5-10分
- 進捗ログで確認可能

### Q5: 初回ログインが失敗する

**A**: note.comのログイン方法を確認
- note.comはSSO（Twitter/Google/Apple）ログインを使用
- 直接のメール/パスワードログインは提供されていない
- 認証状態ファイルの使用を推奨

---

## 1️⃣1️⃣ まとめ

### 移植に必要な最小構成

```
プロジェクトディレクトリ/
├── note_auto_post.js       ← コピー
├── package.json            ← playwright 追加
├── article.md              ← 投稿する記事
└── ~/.note-state.json      ← 認証状態（初回実行後に作成）
```

### 最小限のコマンド

```bash
# 1. 依存関係のインストール
npm install playwright
npx playwright install chromium

# 2. 記事投稿
node note_auto_post.js article.md username password

# 3. 認証状態の確認
ls -lh ~/.note-state.json
```

### 移植成功の確認

✅ ローカルで記事投稿が成功  
✅ 認証状態ファイルが作成された（2833文字）  
✅ 2回目以降の投稿が自動ログインで成功  
✅ 目次が正しく挿入された  
✅ GitHub Actionsで投稿が成功（必要な場合）

---

## 📚 関連ドキュメント

- [RESTORE_POINT.md](RESTORE_POINT.md) - システム全体の復元ポイント
- [README.md](README.md) - プロジェクト概要
- [Playwright Documentation](https://playwright.dev/) - 公式ドキュメント

---

## 📝 更新履歴

- **2025-10-23**: 初版作成
- **2025-10-23**: GitHub Actions対応の修正内容を追加
- **2025-10-23**: トラブルシューティングセクション追加

---

## 👤 作成者

**cantoneseslang**

このガイドは `hongkong-daily-news-note` プロジェクトの実装経験に基づいています。

---

**📄 ライセンス**: All Rights Reserved（このドキュメントを含む）

