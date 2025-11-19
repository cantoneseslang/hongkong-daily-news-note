#!/bin/bash
#
# 今日の記事を再生成するスクリプト
# 使用方法: ./regenerate_today.sh [YYYY-MM-DD]
#
# 引数なしで実行すると今日の日付で再生成
# 引数ありで実行すると指定日付で再生成（例: ./regenerate_today.sh 2025-11-19）
#

set -e

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# 日付を取得（引数があればそれを使用、なければ今日の日付）
if [ -n "$1" ]; then
    TARGET_DATE="$1"
    echo "📅 指定日付: $TARGET_DATE"
else
    TARGET_DATE=$(TZ=Asia/Hong_Kong date +%Y-%m-%d)
    echo "📅 今日の日付 (HKT): $TARGET_DATE"
fi

echo "=" | awk '{for(i=0;i<60;i++)printf"=";printf"\n"}'

# 既存の記事ファイルをバックアップ
ARTICLE_FILE="daily-articles/hongkong-news_${TARGET_DATE}.md"
if [ -f "$ARTICLE_FILE" ]; then
    BACKUP_FILE="${ARTICLE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 既存記事をバックアップ: $BACKUP_FILE"
    cp "$ARTICLE_FILE" "$BACKUP_FILE"
    rm "$ARTICLE_FILE"
fi

# 仮想環境をアクティベート
if [ -d "venv" ]; then
    echo "🔧 仮想環境をアクティベート"
    source venv/bin/activate
fi

# ステップ1: ニュース取得
echo ""
echo "📰 ステップ1: ニュース取得"
echo "=" | awk '{for(i=0;i<60;i++)printf"=";printf"\n"}'
python3 fetch_hongkong_news.py

# 生成されたJSONファイルを確認
RAW_NEWS_FILE="raw_news_${TARGET_DATE}.json"
if [ ! -f "$RAW_NEWS_FILE" ]; then
    echo "❌ エラー: $RAW_NEWS_FILE が見つかりません"
    exit 1
fi

echo "✅ ニュース取得完了: $RAW_NEWS_FILE"

# ステップ2: 記事生成
echo ""
echo "📝 ステップ2: 記事生成"
echo "=" | awk '{for(i=0;i<60;i++)printf"=";printf"\n"}'
python3 generate_article.py "$RAW_NEWS_FILE"

# 生成結果を確認
if [ -f "$ARTICLE_FILE" ]; then
    echo ""
    echo "✅ 記事生成完了！"
    echo "📁 保存先: $ARTICLE_FILE"
    echo ""
    echo "📊 記事情報:"
    echo "  ファイルサイズ: $(wc -c < "$ARTICLE_FILE") bytes"
    echo "  行数: $(wc -l < "$ARTICLE_FILE") lines"
    echo "  ニュース件数: $(grep -c "^### " "$ARTICLE_FILE" || echo 0) 件"
    echo ""
    echo "📝 最初の20行:"
    head -20 "$ARTICLE_FILE"
    echo ""
    echo "=" | awk '{for(i=0;i<60;i++)printf"=";printf"\n"}'
    echo "✅ 記事再生成が完了しました！"
else
    echo "❌ エラー: 記事生成に失敗しました"
    exit 1
fi

