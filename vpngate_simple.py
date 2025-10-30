#!/usr/bin/env python3
"""
VPN Gate 日本サーバー経由で記事生成（簡易版）
システム設定でVPN接続を手動設定後、自動で記事生成
"""

import subprocess
import sys
import time
import json
import os
from datetime import datetime, timedelta, timezone

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class VPNGateSimpleGenerator:
    def __init__(self):
        # VPN Gate 日本サーバー
        self.vpn_servers = [
            "public-vpn-186.opengw.net",
            "public-vpn-120.opengw.net", 
            "public-vpn-75.opengw.net"
        ]
        
    def get_current_country(self):
        """現在の国を取得"""
        try:
            result = subprocess.run([
                "curl", "-s", "--max-time", "5", "https://ipinfo.io/json"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get('country', 'Unknown')
        except:
            pass
        
        return 'Unknown'
    
    def check_vpn_connections(self):
        """利用可能なVPN接続を確認"""
        try:
            result = subprocess.run([
                "scutil", "--nc", "list"
            ], capture_output=True, text=True)
            
            print("利用可能なVPN接続:")
            print(result.stdout)
            
            # 日本VPNを探す
            japan_vpns = []
            for line in result.stdout.split('\n'):
                if 'Japan' in line or 'JP' in line:
                    japan_vpns.append(line.strip())
            
            return japan_vpns
            
        except Exception as e:
            print(f"❌ VPN接続確認エラー: {e}")
            return []
    
    def connect_to_japan_vpn(self):
        """日本VPNに接続"""
        japan_vpns = self.check_vpn_connections()
        
        if not japan_vpns:
            print("❌ 日本VPN接続が見つかりません")
            print("\n📋 手動でVPN設定を行ってください:")
            print("1. システム設定 → ネットワーク")
            print("2. '+' をクリックして新しい接続を追加")
            print("3. インターフェース: VPN")
            print("4. VPNタイプ: L2TP over IPsec")
            print("5. 設定:")
            for server in self.vpn_servers:
                print(f"   - サーバーアドレス: {server}")
                print("   - アカウント名: vpn")
                print("   - パスワード: vpn")
                print("   - 共有シークレット: vpn")
                print()
            return False
        
        # 最初の日本VPNに接続
        vpn_name = japan_vpns[0].split('"')[1] if '"' in japan_vpns[0] else japan_vpns[0]
        
        print(f"🌐 日本VPNに接続中: {vpn_name}")
        
        try:
            result = subprocess.run([
                "scutil", "--nc", "start", vpn_name
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️  VPN接続コマンドエラー: {result.stderr}")
            
            # 接続完了まで待機
            for i in range(30):
                time.sleep(1)
                current_country = self.get_current_country()
                print(f"   接続待機中... ({i+1}/30) - 現在の国: {current_country}")
                
                if current_country == 'JP':
                    print("✅ VPN接続成功（日本から接続）")
                    return True
            
            print("❌ VPN接続タイムアウト")
            return False
            
        except Exception as e:
            print(f"❌ VPN接続エラー: {e}")
            return False
    
    def generate_article_with_vpngate(self, news_file):
        """VPN Gate経由で記事生成"""
        print("=" * 60)
        print("🚀 VPN Gate 日本サーバー経由で記事生成開始")
        print("=" * 60)
        
        # 現在の国を確認
        current_country = self.get_current_country()
        print(f"📍 現在の国: {current_country}")
        
        if current_country == 'JP':
            print("✅ 既に日本からの接続です。記事生成を開始します。")
            return self._run_article_generation(news_file)
        
        # VPN接続
        if not self.connect_to_japan_vpn():
            print("❌ VPN接続に失敗しました")
            return False
        
        # 記事生成
        print(f"\n📝 記事生成開始...")
        success = self._run_article_generation(news_file)
        
        if success:
            print("✅ 記事生成完了")
        else:
            print("❌ 記事生成失敗")
        
        return success
    
    def _run_article_generation(self, news_file):
        """記事生成を実行"""
        try:
            result = subprocess.run([
                "python", "generate_article.py", news_file
            ], cwd=os.getcwd())
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ 記事生成エラー: {e}")
            return False

def main():
    if len(sys.argv) != 2:
        print("使用方法: python vpngate_simple.py <news_file>")
        print("例: python vpngate_simple.py daily-articles/rss_news_2025-10-30_06-12-39.json")
        sys.exit(1)
    
    news_file = sys.argv[1]
    
    if not os.path.exists(news_file):
        print(f"❌ ファイルが見つかりません: {news_file}")
        sys.exit(1)
    
    generator = VPNGateSimpleGenerator()
    success = generator.generate_article_with_vpngate(news_file)
    
    if success:
        print("\n🎉 記事生成が正常に完了しました")
        sys.exit(0)
    else:
        print("\n💥 記事生成に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()
