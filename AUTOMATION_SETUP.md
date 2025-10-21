# 🤖 香港ニュース自動生成セットアップガイド

毎日朝6時に自動でニュース取得→記事生成を実行する設定方法です。

## 📋 機能

- **毎日朝6時に自動実行**
- RSSフィードからニュース取得（136件程度）
- 過去3日分の記事との重複チェック
- 日本語記事を自動生成（30件厳選）
- 記事タイトルの日付を自動修正
- 実行ログを保存

## 🚀 セットアップ方法

### 方法1: launchd（推奨・macOS）

macOSのlaunchdを使って毎日自動実行します。

#### 1. plistファイルを配置

```bash
# plistファイルをLaunchAgentsディレクトリにコピー
cp /Users/sakonhiroki/hongkong-daily-news-note/com.hongkong.dailynews.plist ~/Library/LaunchAgents/
```

#### 2. launchdに登録

```bash
# 登録
launchctl load ~/Library/LaunchAgents/com.hongkong.dailynews.plist

# 確認
launchctl list | grep hongkong
```

#### 3. 登録解除（必要な場合）

```bash
# 登録解除
launchctl unload ~/Library/LaunchAgents/com.hongkong.dailynews.plist
```

#### 4. 手動テスト実行

```bash
# 実行時刻を待たずに今すぐテスト実行
launchctl start com.hongkong.dailynews

# ログを確認
tail -f /Users/sakonhiroki/hongkong-daily-news-note/logs/launchd_stdout.log
```

### 方法2: cron（シンプル）

cronを使った設定方法（launchdの代替）

#### 1. crontabを編集

```bash
crontab -e
```

#### 2. 以下の行を追加

```cron
# 毎日朝6時に香港ニュース生成
0 6 * * * /Users/sakonhiroki/hongkong-daily-news-note/run_daily_news.sh >> /Users/sakonhiroki/hongkong-daily-news-note/logs/cron.log 2>&1
```

#### 3. 保存して確認

```bash
# cron一覧を確認
crontab -l
```

### 方法3: Pythonスケジューラー（手動起動）

scheduler.pyを使って常時実行する方法

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
source venv/bin/activate
python scheduler.py
```

**注意**: この方法はターミナルを開いたままにする必要があります。

## 📊 実行時刻の変更

### launchdの場合

`com.hongkong.dailynews.plist` を編集:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>6</integer>  <!-- この数字を変更 -->
    <key>Minute</key>
    <integer>0</integer>   <!-- この数字を変更 -->
</dict>
```

変更後、再読み込み:

```bash
launchctl unload ~/Library/LaunchAgents/com.hongkong.dailynews.plist
launchctl load ~/Library/LaunchAgents/com.hongkong.dailynews.plist
```

### cronの場合

```cron
# 分 時 日 月 曜日
0 6 * * *  # 毎日6:00
0 8 * * *  # 毎日8:00
30 7 * * * # 毎日7:30
```

## 📝 ログの確認

```bash
# 今日のログを確認
tail -f logs/daily_news_$(date +%Y-%m-%d).log

# launchdのログ
tail -f logs/launchd_stdout.log
tail -f logs/launchd_stderr.log

# 過去のログ一覧
ls -lh logs/
```

## 🧪 テスト実行

### シェルスクリプトを直接実行

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
./run_daily_news.sh
```

### Pythonスクリプトを直接実行

```bash
cd /Users/sakonhiroki/hongkong-daily-news-note
source venv/bin/activate

# ステップ1: ニュース取得
python fetch_rss_news.py

# ステップ2: 記事生成（最新のrss_newsファイルを指定）
python generate_article.py daily-articles/rss_news_2025-10-21_08-49-37.json
```

## 🔧 トラブルシューティング

### 実行されない場合

1. **権限を確認**
   ```bash
   ls -l run_daily_news.sh
   # -rwxr-xr-x であることを確認
   ```

2. **Pythonパスを確認**
   ```bash
   which python
   # venv/bin/python が使われているか確認
   ```

3. **ログを確認**
   ```bash
   cat logs/launchd_stderr.log
   ```

### launchdが動かない場合

```bash
# システム設定 > プライバシーとセキュリティ > フルディスクアクセス
# で、ターミナルやCursorに権限があるか確認
```

## 📮 note.comへの投稿

記事生成後、以下のコマンドで投稿できます：

```bash
cd /Users/sakonhiroki/note-post-mcp
node auto-login-and-draft.js /Users/sakonhiroki/hongkong-daily-news-note/daily-articles/hongkong-news_$(date +%Y-%m-%d).md
```

## 🎯 推奨設定

- **方法**: launchd（方法1）
- **実行時刻**: 朝6:00
- **理由**: 
  - macOSの標準機能で安定
  - 再起動後も自動で実行される
  - ログ管理が簡単

## 📁 ファイル構成

```
hongkong-daily-news-note/
├── run_daily_news.sh              # 自動実行スクリプト
├── com.hongkong.dailynews.plist   # launchd設定ファイル
├── scheduler.py                    # Pythonスケジューラー
├── fetch_rss_news.py              # ニュース取得
├── generate_article.py             # 記事生成
├── logs/                          # 実行ログ
│   ├── daily_news_2025-10-21.log
│   ├── launchd_stdout.log
│   └── launchd_stderr.log
└── daily-articles/                # 記事保存先
    ├── rss_news_*.json
    └── hongkong-news_*.md
```

## ✅ 完了

これで毎日朝6時に自動で：
1. ✅ 136件のニュースを取得
2. ✅ 過去3日分と重複チェック
3. ✅ 30件の日本語記事を生成
4. ✅ 正しい日付で保存

が完了します！

