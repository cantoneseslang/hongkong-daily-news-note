#!/bin/bash

# VPN設定スクリプト
VPN_SERVER="public-vpn-186.opengw.net"
VPN_USER="vpn"
VPN_PASS="vpn"
VPN_SECRET="vpn"

echo "VPN設定を開始します..."

# VPN接続を作成
sudo scutil --nc create "Japan VPN" --interface ppp0 --protocol L2TP --server "$VPN_SERVER" --username "$VPN_USER" --password "$VPN_PASS"

# 共有シークレットを設定
sudo scutil --nc set "Japan VPN" --secret "$VPN_SECRET"

echo "VPN設定完了！"
echo "接続するには: sudo scutil --nc start 'Japan VPN'"
echo "切断するには: sudo scutil --nc stop 'Japan VPN'"
