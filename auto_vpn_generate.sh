#!/bin/bash
# VPN自動接続付き記事生成（シェル版）

NEWS_FILE="$1"
VPN_NAME="Japan VPN"
VPN_SERVER="public-vpn-186.opengw.net"
VPN_USER="vpn"
VPN_PASS="vpn"
VPN_SECRET="vpn"

echo "============================================================"
echo "🚀 VPN自動接続付き記事生成開始"
echo "============================================================"

# 現在の国を確認
echo "📍 現在の国を確認中..."
CURRENT_COUNTRY=$(curl -s --max-time 5 https://ipinfo.io/json | jq -r '.country')
echo "現在の国: $CURRENT_COUNTRY"

VPN_CONNECTED=false

# VPN設定作成
echo "🔧 VPN設定を作成中..."
sudo scutil --nc create "$VPN_NAME" --interface ppp0 --protocol L2TP --server "$VPN_SERVER" --username "$VPN_USER" --password "$VPN_PASS" 2>/dev/null
sudo scutil --nc set "$VPN_NAME" --secret "$VPN_SECRET" 2>/dev/null

# VPN接続（日本以外の場合）
if [ "$CURRENT_COUNTRY" != "JP" ]; then
    echo "🌐 VPN接続中..."
    sudo scutil --nc start "$VPN_NAME"
    
    # 接続完了まで待機
    for i in {1..30}; do
        sleep 1
        NEW_COUNTRY=$(curl -s --max-time 5 https://ipinfo.io/json | jq -r '.country')
        if [ "$NEW_COUNTRY" = "JP" ]; then
            echo "✅ VPN接続成功"
            VPN_CONNECTED=true
            break
        fi
        echo "   接続待機中... ($i/30)"
    done
    
    if [ "$VPN_CONNECTED" = false ]; then
        echo "❌ VPN接続タイムアウト"
        exit 1
    fi
else
    echo "✅ 既に日本からの接続です"
fi

# 記事生成
echo ""
echo "📝 記事生成開始..."
python generate_article.py "$NEWS_FILE"

GENERATE_RESULT=$?

# VPN切断
if [ "$VPN_CONNECTED" = true ]; then
    echo ""
    echo "🔌 VPN切断中..."
    sudo scutil --nc stop "$VPN_NAME"
    
    # 切断完了まで待機
    for i in {1..10}; do
        sleep 1
        NEW_COUNTRY=$(curl -s --max-time 5 https://ipinfo.io/json | jq -r '.country')
        if [ "$NEW_COUNTRY" != "JP" ]; then
            echo "✅ VPN切断完了"
            break
        fi
        echo "   切断待機中... ($i/10)"
    done
fi

echo "============================================================"
echo "🏁 VPN自動接続付き記事生成終了"
echo "============================================================"

if [ $GENERATE_RESULT -eq 0 ]; then
    echo "🎉 記事生成が正常に完了しました"
    exit 0
else
    echo "💥 記事生成に失敗しました"
    exit 1
fi



