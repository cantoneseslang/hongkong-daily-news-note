#!/bin/bash
# GPT-4 API使用記事生成（VPN手動接続必須）

echo "============================================================"
echo "🚀 OpenAI GPT-4 APIで記事生成"
echo "============================================================"

# VPN接続状態確認
echo "📍 現在の接続状態を確認中..."
COUNTRY=$(curl -s --max-time 5 https://ipinfo.io/json | jq -r '.country')
echo "現在の国: $COUNTRY"

if [ "$COUNTRY" != "JP" ]; then
    echo ""
    echo "⚠️  日本（JP）からの接続が必要です"
    echo "手順:"
    echo "1. システム環境設定 > ネットワーク > Japan VPN"
    echo "2. 接続ボタンをクリック"
    echo ""
    read -p "VPN接続が完了したらEnterを押してください..."
    
    # 再接続状態確認
    COUNTRY=$(curl -s --max-time 5 https://ipinfo.io/json | jq -r '.country')
    if [ "$COUNTRY" != "JP" ]; then
        echo "❌ 日本（JP）からの接続ではありません: $COUNTRY"
        exit 1
    fi
    echo "✅ 日本からの接続を確認しました"
fi

# OpenAI API設定に戻す
echo ""
echo "🔧 OpenAI API設定を有効化中..."
cat > generate_article.tmp.py << 'PYTHON_CODE'
# API設定を一時的に変更
import json
import re

# generate_article.pyを読み込んで修正
with open('generate_article.py', 'r', encoding='utf-8') as f:
    content = f.read()

# OpenAI API使用に変更
content = re.sub(
    r'# Grok API使用.*?self\.use_openai = None',
    '# OpenAI API使用\n        if os.environ.get("USE_OPENAI") == "1":\n            self.api_key = self.config[\'openai_api\'][\'api_key\']\n            self.api_url = self.config[\'openai_api\'][\'api_url\']\n            self.use_openai = True\n        else:\n            self.api_key = self.config[\'grok_api\'][\'api_key\']\n            self.api_url = self.config[\'grok_api\'][\'api_url\']\n            self.use_openai = None',
    content,
    flags=re.DOTALL
)

with open('generate_article.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ OpenAI API設定を有効化しました")
PYTHON_CODE

python3 -c "$(cat generate_article.tmp.py)"
rm generate_article.tmp.py

# 記事生成
echo ""
echo "📝 記事生成開始..."
source venv/bin/activate
export USE_OPENAI=1
python generate_article.py "$1"

GENERATE_RESULT=$?

echo ""
echo "============================================================"
if [ $GENERATE_RESULT -eq 0 ]; then
    echo "🎉 記事生成が正常に完了しました"
else
    echo "💥 記事生成に失敗しました"
fi
echo "============================================================"

exit $GENERATE_RESULT
