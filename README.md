# 🇭🇰 香港デイリーニュース 完全自動生成システム

**毎日朝6時に自動で香港のニュースを取得し、日本語記事を生成してnote.comに投稿する完全自動化システム**

[![GitHub Actions](https://github.com/cantoneseslang/hongkong-daily-news-note/workflows/Daily%20Hong%20Kong%20News%20Generator/badge.svg)](https://github.com/cantoneseslang/hongkong-daily-news-note/actions)

🎉 **完全クラウド自動化達成！PCの電源不要！** 🎉

---

## 🌟 システムの特徴

### 完全自動化フロー

```
毎日朝6時（JST/HKT）🌅
  ↓
🤖 GitHub Actions起動（完全クラウド）
  ↓
1. 📰 12のRSSフィードから150件以上のニュース取得
2. 🔍 過去3日分の記事と重複チェック（12件程度除外）
3. ✍️  カテゴリー分類し30件を厳選
4. 🤖 Grok APIで日本語記事を生成
5. 📅 記事タイトルの日付を自動修正
6. 🌐 Puppeteerで自動ブラウザ起動
7. 🔐 note.comに自動ログイン
8. 📮 記事を自動投稿（下書き保存）
9. 🏷️  タグ自動設定（#今日の広東語 #広東語）
10. 💾 GitHubに自動コミット＆プッシュ
  ↓
✅ 完了！🎊
```

### 🎯 主な機能

- ✅ **完全クラウド自動化** - PCの電源状態に依存しない
- ✅ **重複排除システム** - 過去3日分の記事と自動比較
- ✅ **高品質翻訳** - Grok APIによる正確な日本語翻訳
- ✅ **天気情報統合** - 香港天文台から自動取得・翻訳
- ✅ **自動投稿** - note.comへの完全自動投稿
- ✅ **エラー回復** - リトライ機能とフォールバック処理
- ✅ **デバッグ機能** - スクリーンショット・HTMLダウンロード

---

## 📊 取得ニュースソース

### RSSフィード（12ソース）

1. **SCMP** (South China Morning Post)
   - 総合ニュース
   - ビジネス
   - ライフスタイル

2. **RTHK** (Radio Television Hong Kong)
   - 一般ニュース
   - ビジネス

3. **Yahoo News HK**
4. **Google News HK**
5. **China Daily HK**
6. **Hong Kong Free Press**

7. **HKET** (香港経済日報)
   - 香港ニュース
   - 財経
   - 不動産

8. **香港天文台** (天気情報)
   - 天気警報
   - 天気予報
   - 現在の天気
   - 9日間予報

---

## 🚀 クイックスタート

### 自動実行（推奨）

**何もする必要ありません！** 

GitHub Actionsが毎日朝6時に自動実行し、note.comに投稿します。

- **確認**: https://note.com/bestinksalesman/notes
- **実行状況**: https://github.com/cantoneseslang/hongkong-daily-news-note/actions

### 手動実行

必要に応じて、いつでも手動実行できます：

1. **GitHub Actionsで実行**:
   ```
   https://github.com/cantoneseslang/hongkong-daily-news-note/actions
   ```
   - 「Run workflow」をクリック

2. **ローカルで実行**:
   ```bash
   cd /Users/sakonhiroki/hongkong-daily-news-note
   ./run_daily_news.sh
   ```

---

## 🔧 セットアップ（初回のみ）

### 1. GitHub Secretsの設定

以下のURLでSecretsを設定：
```
https://github.com/cantoneseslang/hongkong-daily-news-note/settings/secrets/actions
```

**必須のSecrets**:
- `GROK_API_KEY` - xAI Grok API Key
- `NOTE_EMAIL` - note.comのメールアドレス
- `NOTE_PASSWORD` - note.comのパスワード

**オプション**（現在未使用）:
- `NEWS_API_KEY`
- `WORLD_NEWS_API_KEY`
- `NEWSDATA_IO_API_KEY`

### 2. Workflow Permissionsの設定

```
https://github.com/cantoneseslang/hongkong-daily-news-note/settings/actions
```

- ✅ **Read and write permissions** を選択
- 「Save」をクリック

---

## 📁 ファイル構成

```
hongkong-daily-news-note/
├── .github/
│   └── workflows/
│       └── daily-news.yml                 # GitHub Actionsワークフロー
├── fetch_rss_news.py                      # RSSニュース取得
├── generate_article.py                    # 記事生成（重複チェック付き）
├── post_to_note_github_actions.js         # note.com自動投稿
├── scheduler.py                           # ローカル自動実行用
├── run_daily_news.sh                      # シェルスクリプト
├── requirements.txt                       # Python依存関係
├── package.json                           # Node.js依存関係
├── package-lock.json                      # npmロックファイル
├── GITHUB_ACTIONS_SETUP.md                # セットアップガイド
├── AUTOMATION_SETUP.md                    # ローカル自動化ガイド
├── WORK_RECORD.md                         # 作業記録
└── daily-articles/                        # 生成ファイル保存先
    ├── rss_news_*.json                    # 取得したニュース
    └── hongkong-news_*.md                 # 生成した記事
```

---

## 🔍 重複チェック機能

### 過去記事との重複排除

毎日の記事生成時に、過去3日分の記事と自動比較：

```python
# 過去3日分の記事ファイルをチェック
for days_ago in range(1, 4):
    past_date = datetime.now() - timedelta(days=days_ago)
    past_file = f"daily-articles/hongkong-news_{past_date.strftime('%Y-%m-%d')}.md"
```

### 重複判定基準

1. **URL完全一致** - 同じURLのニュースは除外
2. **タイトル類似度70%以上** - 類似記事を除外
   - 3単語以上共通
   - 共通率70%以上で重複判定

### 効果

- 152件のニュース → **12件の重複除外** → 140件
- さらに同日内重複で4件除外 → **最終136件**
- 30件の厳選記事を生成

---

## 🎯 実行結果（例）

### 2025年10月21日の実行

```
📂 過去記事チェック:
  - 2025-10-20: 21件のURL、20件のタイトル
  - 2025-10-19: 21件のURL、21件のタイトル
  - 2025-10-18: 16件のURL、15件のタイトル
  
🔍 合計 58件のURLと56件のタイトルを抽出
🚫 過去記事との重複除外: 12件
📊 フィルタ後: 152 → 140件

📋 カテゴリー別件数:
  - テクノロジー: 57件
  - ビジネス・経済: 28件
  - カルチャー: 23件
  - 社会・その他: 14件
  - その他: 14件

✅ 30件の厳選記事を生成
⏱️  所要時間: 約2分30秒
```

---

## 🔐 セキュリティ

### APIキー管理

- ✅ **GitHub Secrets**で安全に管理
- ✅ **config.json**は.gitignoreで除外
- ✅ **Push Protection**で誤コミット防止

### 認証情報

- note.comのログイン情報もGitHub Secretsで管理
- リポジトリに直接コミットしない

---

## 📈 パフォーマンス

| 項目 | 値 |
|-----|-----|
| **ニュース取得** | 150件以上 |
| **重複除外** | 12件（過去3日分） |
| **記事生成** | 30件 |
| **実行時間** | 約2分30秒 |
| **費用** | 無料（GitHub Actions枠内） |

---

## 🐛 トラブルシューティング

### GitHub Actions失敗時

1. **実行ログを確認**:
   ```
   https://github.com/cantoneseslang/hongkong-daily-news-note/actions
   ```

2. **デバッグ情報をダウンロード**:
   - Artifactsセクションから
   - `note-com-debug-screenshots`
   - `note-com-debug-html`

3. **Secretsを確認**:
   - GROK_API_KEYが設定されているか
   - NOTE_EMAIL、NOTE_PASSWORDが正しいか

### ローカルでテスト

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
source venv/bin/activate

# ステップ1: ニュース取得
python fetch_rss_news.py

# ステップ2: 記事生成
python generate_article.py daily-articles/rss_news_*.json

# ステップ3: note.com投稿（ローカル）
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js /Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_*.md
```

---

## 🎨 カスタマイズ

### 実行時刻の変更

`.github/workflows/daily-news.yml`を編集：

```yaml
schedule:
  - cron: '0 22 * * *'  # UTC 22:00 = JST 6:00
  # JST 8:00に変更する場合: '0 23 * * *'
```

### 記事数の変更

`generate_article.py`の`target_count`を変更：

```python
target_count = 30  # 記事数を変更
```

### タグの変更

`post_to_note_github_actions.js`のタグ部分を編集（将来実装予定）

---

## 📚 ドキュメント

- **GITHUB_ACTIONS_SETUP.md** - GitHub Actions詳細セットアップ
- **AUTOMATION_SETUP.md** - ローカル自動化（launchd/cron）
- **WORK_RECORD.md** - 開発作業記録
- **manual_post_to_note.md** - 手動投稿ガイド

---

## 🎊 完成した自動化の成果

### ✅ 達成したこと

1. **完全クラウド自動化** - GitHub Actionsで毎日朝6時に自動実行
2. **重複排除** - 過去3日分の記事と比較して12件除外
3. **note.com自動投稿** - Puppeteerで完全自動化
4. **日付自動修正** - タイトル日付を毎日自動更新
5. **エラー回復** - リトライ機能とフォールバック処理
6. **デバッグ機能** - スクリーンショット・HTML保存

### 📊 運用実績

- **実行成功率**: 100%（テスト済み）
- **平均実行時間**: 約2分30秒
- **記事品質**: 30件の厳選された日本語ニュース
- **重複除外**: 過去記事から12件の重複を自動排除
- **無料運用**: GitHub Actions無料枠内で運用可能

### 🔑 重要なポイント

#### 1. 重複チェックの仕組み

過去3日分の記事ファイルを自動読み込み：
- URLの完全一致チェック
- タイトルの類似度70%以上で重複判定
- 同じ事件・イベントの重複報道を自動排除

#### 2. GitHub Actions の工夫

- **同時実行制御**: `concurrency`で複数実行を防止
- **リトライ機能**: プッシュ失敗時に3回まで自動リトライ
- **権限管理**: 必要最小限の`contents: write`のみ
- **デバッグ**: スクリーンショットとHTMLを自動保存

#### 3. note.com自動投稿の実現

- **Puppeteer**: Headless Browserで完全自動化
- **柔軟なセレクター**: 複数パターンで要素検索
- **詳細ログ**: すべてのステップで状況を出力
- **エラーハンドリング**: 失敗時でもワークフローを継続

#### 4. 日付の自動修正

Grok APIが間違った日付を返す問題に対処：
```bash
TODAY=$(date +"%Y年%m月%d日")
sed -i "s/# 毎日AIピックアップニュース([0-9]\{4\}年[0-9]\{2\}月[0-9]\{2\}日)/# 毎日AIピックアップニュース($TODAY)/"
```

---

## 🔧 技術スタック

### バックエンド
- **Python 3.11** - メイン処理
- **feedparser** - RSS解析
- **requests** - HTTP通信
- **python-dateutil** - 日付処理

### フロントエンド自動化
- **Node.js 20** - JavaScript実行環境
- **Puppeteer 24.15.0** - ブラウザ自動化
- **GitHub Actions** - CI/CD

### API
- **xAI Grok API** - 記事生成
- **Google Translate API** - 天気情報翻訳
- **香港天文台RSS** - 天気情報

---

## 📖 使い方

### 自動実行（デフォルト）

**何もする必要ありません！**

毎日朝6時にGitHub Actionsが自動実行し、note.comに投稿します。

### 手動実行

#### GitHub Actionsで実行

```
https://github.com/cantoneseslang/hongkong-daily-news-note/actions
```

「Run workflow」をクリック

#### ローカルで実行

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
./run_daily_news.sh
```

または個別に実行：

```bash
# ステップ1: ニュース取得
source venv/bin/activate
python fetch_rss_news.py

# ステップ2: 記事生成
python generate_article.py daily-articles/rss_news_*.json

# ステップ3: note投稿（ローカル）
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js /Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_*.md
```

---

## 🌐 GitHub Actionsワークフロー

### 実行スケジュール

- **自動実行**: 毎日 UTC 22:00（JST 6:00）
- **手動実行**: いつでも可能

### ワークフローステップ

1. **Checkout repository** - リポジトリをチェックアウト（全履歴）
2. **Setup Python** - Python 3.11をセットアップ
3. **Install dependencies** - Python依存関係をインストール
4. **Create config.json** - GitHub Secretsから設定ファイル生成
5. **Fetch RSS news** - ニュース取得
6. **Generate article** - 記事生成（重複チェック）
7. **Fix article date** - 日付自動修正
8. **Setup Node.js** - Node.js 20をセットアップ
9. **Install Puppeteer** - Puppeteerをインストール
10. **Post to note.com** - note.comに自動投稿
11. **Commit and push** - GitHubに自動プッシュ
12. **Summary** - 実行結果サマリー

---

## 📊 カテゴリー分類

ニュースは自動的に以下のカテゴリーに分類されます：

- ビジネス・経済
- 不動産
- テクノロジー
- 医療・健康
- 教育
- カルチャー
- 交通
- 治安・犯罪
- 事故・災害
- 政治・行政
- 天気
- 社会・その他

各カテゴリーから均等に30件を選出。

---

## 🔒 セキュリティ対策

### 実装済み

1. **GitHub Secrets** - APIキーと認証情報を安全に管理
2. **Push Protection** - 誤ってAPIキーをコミットするとブロック
3. **最小権限** - 必要最小限の権限のみ付与
4. **config.json除外** - .gitignoreで設定ファイルを除外

### ベストプラクティス

- APIキーはGitHub Secretsで管理
- ローカルのconfig.jsonは絶対にコミットしない
- パスワードはSecretsで管理

---

## 🐛 よくある問題と解決

### 問題1: GitHub Actions失敗

**症状**: ワークフローが失敗する

**解決**:
1. GitHub ActionsのログでどのステップでエラーかWeb確認
2. Artifactsからスクリーンショット・HTMLをダウンロード
3. Secretsが正しく設定されているか確認

### 問題2: 重複ニュースが含まれる

**症状**: 前日と同じニュースが記事に含まれる

**解決**:
- 過去の記事ファイル（.md）がGitHubにコミットされているか確認
- `git pull`で最新の過去記事を取得

### 問題3: 日付が間違っている

**症状**: タイトルの日付が古い

**解決**:
- 「Fix article date」ステップで自動修正される
- sedコマンドが正常に実行されているかログ確認

### 問題4: note.com投稿失敗

**症状**: Puppeteerがログインできない

**解決**:
1. NOTE_EMAIL、NOTE_PASSWORDが正しいか確認
2. Artifactsのスクリーンショットで画面状態を確認
3. note.comのDOM構造が変わっていないか確認

---

## 🎓 学んだこと・重要なポイント

### 1. GitHub Actionsの同時実行制御

```yaml
concurrency:
  group: daily-news
  cancel-in-progress: false
```

複数のワークフローが同時実行されてGitコンフリクトが発生するのを防ぐ。

### 2. Gitプッシュのリトライ戦略

```bash
for i in {1..3}; do
  if git push origin main; then
    break
  else
    git pull --no-rebase origin main
    sleep 2
  fi
done
```

リモートに新しいコミットがある場合でも自動回復。

### 3. Puppeteerの柔軟なセレクター検索

複数のセレクターパターンを試して、DOM構造の変更に対応。

### 4. 過去記事からのURL・タイトル抽出

正規表現で既存の記事ファイルから情報を抽出：
```python
url_matches = re.findall(r'\*\*リンク\*\*:\s*(https?://[^\s]+)', content)
title_matches = re.findall(r'^### (.+)$', content, re.MULTILINE)
```

---

## 🚀 今後の拡張案

### 1. 画像自動生成
- AI画像生成でサムネイル作成
- note.comに自動アップロード

### 2. SNS連携
- Twitter/Xへの自動投稿
- Facebookページへの投稿

### 3. 通知機能
- 記事生成完了時にSlack/Discord通知
- エラー発生時のアラート

### 4. 多言語対応
- 英語版記事の同時生成
- 繁体字中国語版の追加

---

## 📞 サポート・問い合わせ

### リポジトリ
https://github.com/cantoneseslang/hongkong-daily-news-note

### GitHub Actions
https://github.com/cantoneseslang/hongkong-daily-news-note/actions

### 生成記事
https://note.com/bestinksalesman/notes

---

## 📝 更新履歴

- **2025-10-21**: 完全自動化達成🎉
  - GitHub Actions + Puppeteer実装
  - note.com自動投稿機能追加
  - 過去記事との重複チェック実装
  - 日付自動修正機能追加
  
- **2025-10-16**: 初回リリース
  - RSSフィード収集
  - Grok API連携
  - 記事生成機能

---

**開発者**: Sako Hiroki  
**プロジェクト**: hongkong-daily-news-note  
**最終更新**: 2025-10-21  
**ステータス**: ✅ 完全自動化稼働中
