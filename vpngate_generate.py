#!/usr/bin/env python3
"""
VPN Gate 日本サーバー経由で記事生成
提供された3つの日本サーバーを使用
"""

import subprocess
import sys
import time
import json
import os
from datetime import datetime, timedelta, timezone

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class VPNGateArticleGenerator:
    def __init__(self):
        # VPN Gate 日本サーバー（優先順位順）
        self.vpn_servers = [
            {
                "name": "Japan VPN 186",
                "server": "public-vpn-186.opengw.net",
                "ip": "219.100.37.163",
                "protocol": "L2TP"
            },
            {
                "name": "Japan VPN 120", 
                "server": "public-vpn-120.opengw.net",
                "ip": "219.100.37.101",
                "protocol": "L2TP"
            },
            {
                "name": "Japan VPN 75",
                "server": "public-vpn-75.opengw.net", 
                "ip": "219.100.37.24",
                "protocol": "L2TP"
            }
        ]
        
        # VPN Gate 共通認証情報
        self.vpn_user = "vpn"
        self.vpn_pass = "vpn"
        self.vpn_secret = "vpn"
        
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
    
    def setup_vpn_connection(self, server_info):
        """VPN接続を設定"""
        vpn_name = server_info["name"]
        server = server_info["server"]
        
        print(f"🔧 VPN設定を作成中: {vpn_name}")
        
        try:
            # 既存の接続を削除
            subprocess.run([
                "scutil", "--nc", "remove", vpn_name
            ], capture_output=True)
            
            # L2TP接続を作成
            result = subprocess.run([
                "scutil", "--nc", "create", vpn_name,
                "--interface", "ppp0",
                "--protocol", "L2TP", 
                "--server", server,
                "--username", self.vpn_user,
                "--password", self.vpn_pass
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # 共有シークレットを設定
                subprocess.run([
                    "scutil", "--nc", "set", vpn_name,
                    "--secret", self.vpn_secret
                ], capture_output=True)
                
                print(f"✅ VPN設定完了: {vpn_name}")
                return True
            else:
                print(f"❌ VPN設定失敗: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ VPN設定エラー: {e}")
            return False
    
    def connect_vpn(self, server_info):
        """VPN接続"""
        vpn_name = server_info["name"]
        
        print(f"🌐 VPN接続中: {vpn_name}")
        
        try:
            # VPN接続
            result = subprocess.run([
                "scutil", "--nc", "start", vpn_name
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️  VPN接続コマンドエラー: {result.stderr}")
            
            # 接続完了まで待機
            for i in range(30):  # 最大30秒待機
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
    
    def disconnect_vpn(self, server_info):
        """VPN切断"""
        vpn_name = server_info["name"]
        
        print(f"🔌 VPN切断中: {vpn_name}")
        
        try:
            subprocess.run([
                "scutil", "--nc", "stop", vpn_name
            ], capture_output=True)
            
            # 切断完了まで待機
            for i in range(10):
                time.sleep(1)
                current_country = self.get_current_country()
                if current_country != 'JP':
                    print("✅ VPN切断完了")
                    return True
                print(f"   切断待機中... ({i+1}/10)")
            
            print("⚠️  VPN切断タイムアウト")
            return True
            
        except Exception as e:
            print(f"⚠️  VPN切断エラー: {e}")
            return True
    
    def generate_article_with_vpngate(self, news_file):
        """VPN Gate経由で記事生成"""
        print("=" * 60)
        print("🚀 VPN Gate 日本サーバー経由で記事生成開始")
        print("=" * 60)
        
        # 現在の国を確認
        current_country = self.get_current_country()
        print(f"📍 現在の国: {current_country}")
        
        if current_country == 'JP':
            print("✅ 既に日本からの接続です。VPN接続をスキップします。")
            return self._run_article_generation(news_file)
        
        # 各VPNサーバーを試行
        for i, server_info in enumerate(self.vpn_servers, 1):
            print(f"\n🔄 VPNサーバー {i}/{len(self.vpn_servers)} を試行中...")
            print(f"   サーバー: {server_info['server']}")
            print(f"   IP: {server_info['ip']}")
            
            vpn_connected = False
            
            try:
                # VPN設定
                if not self.setup_vpn_connection(server_info):
                    print(f"❌ VPN設定失敗: {server_info['name']}")
                    continue
                
                # VPN接続
                if not self.connect_vpn(server_info):
                    print(f"❌ VPN接続失敗: {server_info['name']}")
                    continue
                
                vpn_connected = True
                
                # 記事生成
                print(f"\n📝 記事生成開始（{server_info['name']}経由）...")
                success = self._run_article_generation(news_file)
                
                if success:
                    print("✅ 記事生成完了")
                    return True
                else:
                    print("❌ 記事生成失敗")
                
            except Exception as e:
                print(f"❌ エラー発生: {e}")
            
            finally:
                # VPN切断
                if vpn_connected:
                    self.disconnect_vpn(server_info)
        
        print("\n❌ すべてのVPNサーバーで記事生成に失敗しました")
        return False
    
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
        print("使用方法: python vpngate_generate.py <news_file>")
        print("例: python vpngate_generate.py daily-articles/rss_news_2025-10-30_06-12-39.json")
        sys.exit(1)
    
    news_file = sys.argv[1]
    
    if not os.path.exists(news_file):
        print(f"❌ ファイルが見つかりません: {news_file}")
        sys.exit(1)
    
    generator = VPNGateArticleGenerator()
    success = generator.generate_article_with_vpngate(news_file)
    
    if success:
        print("\n🎉 記事生成が正常に完了しました")
        sys.exit(0)
    else:
        print("\n💥 記事生成に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()
