#!/bin/bash
# VPN設定自動作成スクリプト

VPN_NAME="Japan VPN"
VPN_SERVER="public-vpn-186.opengw.net"
VPN_USER="vpn"
VPN_PASS="vpn"
VPN_SECRET="vpn"

echo "🔧 VPN設定を自動作成中..."

# 既存のVPN設定を削除（存在する場合）
sudo scutil --nc remove "$VPN_NAME" 2>/dev/null

# VPN設定を作成
echo "📝 VPN接続を作成中..."
sudo scutil --nc create "$VPN_NAME" --interface ppp0 --protocol L2TP --server "$VPN_SERVER" --username "$VPN_USER" --password "$VPN_PASS"

if [ $? -eq 0 ]; then
    echo "✅ VPN接続作成成功"
else
    echo "❌ VPN接続作成失敗"
    exit 1
fi

# 共有シークレットを設定
echo "🔐 共有シークレットを設定中..."
sudo scutil --nc set "$VPN_NAME" --secret "$VPN_SECRET"

if [ $? -eq 0 ]; then
    echo "✅ 共有シークレット設定成功"
else
    echo "❌ 共有シークレット設定失敗"
    exit 1
fi

echo ""
echo "🎉 VPN設定が完了しました！"
echo "設定名: $VPN_NAME"
echo "サーバー: $VPN_SERVER"
echo "ユーザー: $VPN_USER"
echo "パスワード: $VPN_PASS"
echo "共有シークレット: $VPN_SECRET"
echo ""
echo "これで自動記事生成が使用できます:"
echo "python auto_vpn_generate.py daily-articles/rss_news_2025-10-28_09-37-28.json"



