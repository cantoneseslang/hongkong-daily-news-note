#!/bin/bash
# 完全な記事生成パイプラインのテストスクリプト

set -e

echo "=================================================================================="
echo "🚀 完全な記事生成パイプラインのテスト"
echo "=================================================================================="
echo ""

# 仮想環境のパス
VENV_PATH="venv/bin/activate"

# テスト日時を設定（明日の朝6時をシミュレート）
TEST_DATE=$(date -v+1d -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 06:00:00" +%Y-%m-%d)
echo "📅 テスト実行日時: $(date)"
echo "📅 シミュレート日時: ${TEST_DATE} 06:00:00"
echo ""

# 1. RSSニュース取得のテスト
echo "=================================================================================="
echo "1️⃣ RSSニュース取得のテスト"
echo "=================================================================================="
echo ""

source "$VENV_PATH"
python3 fetch_rss_news.py

if [ $? -ne 0 ]; then
    echo "❌ RSSニュース取得に失敗しました"
    exit 1
fi

echo ""
echo "✅ RSSニュース取得成功"
echo ""

# 2. 最新のJSONファイルを取得
LATEST_JSON=$(ls -t daily-articles/rss_news_*.json | head -1)
echo "📂 最新のJSONファイル: $LATEST_JSON"
echo ""

# 3. 記事生成のテスト
echo "=================================================================================="
echo "2️⃣ 記事生成のテスト（天気予報翻訳含む）"
echo "=================================================================================="
echo ""

python3 generate_article.py "$LATEST_JSON"

if [ $? -ne 0 ]; then
    echo "❌ 記事生成に失敗しました"
    exit 1
fi

echo ""
echo "✅ 記事生成成功"
echo ""

# 4. 生成された記事ファイルを確認
GENERATED_ARTICLE=$(ls -t daily-articles/hongkong-news_*.md | head -1)
echo "📄 生成された記事ファイル: $GENERATED_ARTICLE"
echo ""

# 5. 広東語/中文のチェック
echo "=================================================================================="
echo "3️⃣ 生成された記事の広東語/中文チェック"
echo "=================================================================================="
echo ""

python3 << 'PYTHON_SCRIPT'
import re
import sys

def has_chinese_chars(text):
    if not text:
        return False
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))

# 生成された記事ファイルを読み込む
import glob
import os
article_files = glob.glob("daily-articles/hongkong-news_*.md")
if not article_files:
    print("❌ 生成された記事ファイルが見つかりません")
    sys.exit(1)

latest_article = max(article_files, key=os.path.getctime)
print(f"📂 チェック対象: {latest_article}")
print()

with open(latest_article, 'r', encoding='utf-8') as f:
    content = f.read()

# 日本語マーカーを除外
japanese_markers = ['本日の香港の天気', '天気予報', '引用元', '香港天文台', '翻訳エラー',
                   '###', '##', '#', '毎日AIピックアップニュース', '広東語学習者向け',
                   'スラング先生', 'LINE', '広東語|']

lines = content.split('\n')
problematic_lines = []
for i, line in enumerate(lines, 1):
    if has_chinese_chars(line):
        is_japanese = any(marker in line for marker in japanese_markers)
        if not is_japanese and len(line.strip()) > 10:
            problematic_lines.append((i, line[:200]))

if problematic_lines:
    print("❌ エラー: 記事に広東語/中文が含まれています！")
    print()
    print("広東語/中文が含まれている箇所（最初の10箇所）:")
    for line_num, line_content in problematic_lines[:10]:
        print(f"  行{line_num}: {line_content}")
    sys.exit(1)
else:
    print("✅ 記事に広東語/中文は含まれていません")
    print()

# 天気情報セクションがあるか確認
if "## 本日の香港の天気" in content:
    print("✅ 天気情報セクションが含まれています")
    
    # 天気情報セクションの内容を確認
    weather_section_start = content.find("## 本日の香港の天気")
    weather_section = content[weather_section_start:weather_section_start+1000]
    
    if "[翻訳エラー" in weather_section:
        print("⚠️  警告: 天気情報に翻訳エラーが含まれています")
        print("   APIキーが無効な可能性があります")
    elif has_chinese_chars(weather_section):
        # 日本語マーカーを除外して再チェック
        weather_lines = weather_section.split('\n')
        has_problem = False
        for line in weather_lines:
            if has_chinese_chars(line):
                is_japanese = any(marker in line for marker in japanese_markers)
                if not is_japanese:
                    has_problem = True
                    break
        
        if has_problem:
            print("❌ エラー: 天気情報セクションに広東語/中文が含まれています！")
            sys.exit(1)
        else:
            print("✅ 天気情報セクションは正しく翻訳されています")
    else:
        print("✅ 天気情報セクションは正しく翻訳されています")
else:
    print("⚠️  天気情報セクションが見つかりません")

print()
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo "❌ 広東語/中文チェックに失敗しました"
    exit 1
fi

echo ""
echo "=================================================================================="
echo "✅ すべてのテストが完了しました"
echo "=================================================================================="
echo ""
echo "📝 テスト結果のサマリー:"
echo "  ✅ RSSニュース取得: 成功"
echo "  ✅ 記事生成: 成功"
echo "  ✅ 広東語/中文チェック: 成功"
echo ""
echo "⚠️  注意: 実際のAPIキーが必要です"
echo "   明日の朝6時の実行時には、config.jsonに有効なAPIキーが"
echo "   設定されていることを確認してください。"
echo ""



