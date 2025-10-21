#!/bin/bash
# 香港ニュース自動生成スクリプト
# 毎日朝6時に実行

# スクリプトのディレクトリに移動
cd /Users/sakonhiroki/hongkong-daily-news-note

# ログディレクトリ作成
mkdir -p logs

# ログファイル
LOG_FILE="logs/daily_news_$(date +%Y-%m-%d).log"

echo "========================================" >> "$LOG_FILE"
echo "開始時刻: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 仮想環境を有効化して実行
source venv/bin/activate

# 1. RSSフィードからニュース取得
echo "📰 ニュース取得開始..." >> "$LOG_FILE"
python fetch_rss_news.py >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ ニュース取得失敗" >> "$LOG_FILE"
    exit 1
fi

# 最新のRSSニュースファイルを取得
LATEST_RSS=$(ls -t daily-articles/rss_news_*.json | head -1)
echo "✅ ニュースファイル: $LATEST_RSS" >> "$LOG_FILE"

# 2. 記事生成（過去記事との重複チェック付き）
echo "✍️  記事生成開始..." >> "$LOG_FILE"
python generate_article.py "$LATEST_RSS" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ 記事生成失敗" >> "$LOG_FILE"
    exit 1
fi

# 最新の記事ファイルを取得
LATEST_ARTICLE=$(ls -t daily-articles/hongkong-news_*.md | head -1)
echo "✅ 記事ファイル: $LATEST_ARTICLE" >> "$LOG_FILE"

# 3. 日付の自動修正
echo "📅 記事タイトルの日付を修正..." >> "$LOG_FILE"
TODAY=$(date +"%Y年%m月%d日")
sed -i.bak "s/# 毎日AIピックアップニュース([0-9]\{4\}年[0-9]\{2\}月[0-9]\{2\}日)/# 毎日AIピックアップニュース($TODAY)/" "$LATEST_ARTICLE"
rm "${LATEST_ARTICLE}.bak"
echo "✅ タイトル日付を $TODAY に修正しました" >> "$LOG_FILE"

echo "========================================" >> "$LOG_FILE"
echo "✅ 完了時刻: $(date)" >> "$LOG_FILE"
echo "📁 記事パス: $LATEST_ARTICLE" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 成功通知（オプション）
# osascript -e 'display notification "香港ニュース記事が生成されました" with title "Daily News"'

exit 0

