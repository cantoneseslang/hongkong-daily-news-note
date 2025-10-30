#!/usr/bin/env python3
"""
VPN Gate 動的サーバー取得・接続スクリプト
vpngate.net から最新の日本サーバー情報を取得して接続
"""

import subprocess
import sys
import time
import json
import os
import re
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class VPNGateDynamicGenerator:
    def __init__(self):
        self.vpngate_url = "https://www.vpngate.net/ja/"
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
    
    def fetch_japan_servers(self):
        """VPN Gate から日本サーバー情報を取得"""
        print("🌐 VPN Gate から日本サーバー情報を取得中...")
        
        try:
            # VPN Gate サイトにアクセス
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(self.vpngate_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # HTMLをパース
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # テーブルから日本サーバーを抽出
            japan_servers = []
            
            # テーブル行を検索
            rows = soup.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    # 日本フラグをチェック
                    flag_img = cells[0].find('img')
                    if flag_img and 'JP' in flag_img.get('src', ''):
                        # サーバー情報を抽出
                        server_info = self._extract_server_info(cells)
                        if server_info:
                            japan_servers.append(server_info)
            
            print(f"✅ {len(japan_servers)} 個の日本サーバーを発見")
            return japan_servers
            
        except Exception as e:
            print(f"❌ サーバー情報取得エラー: {e}")
            # フォールバック用の固定サーバー
            return [
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
    
    def _extract_server_info(self, cells):
        """テーブルセルからサーバー情報を抽出"""
        try:
            # DDNS名/IPアドレスを抽出
            server_cell = cells[1]
            server_text = server_cell.get_text(strip=True)
            
            # サーバー名とIPを抽出
            lines = server_text.split('\n')
            server_name = lines[0].strip() if lines else ""
            ip_address = ""
            
            # IPアドレスを検索
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', server_text)
            if ip_match:
                ip_address = ip_match.group(1)
            
            if server_name and ip_address:
                return {
                    "name": f"Japan VPN {server_name.split('-')[-1] if '-' in server_name else 'Dynamic'}",
                    "server": server_name,
                    "ip": ip_address,
                    "protocol": "L2TP"
                }
                
        except Exception as e:
            print(f"⚠️  サーバー情報抽出エラー: {e}")
        
        return None
    
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
    
    def create_vpn_connection(self, server_info):
        """VPN接続を作成（macOS）"""
        vpn_name = server_info["name"]
        server = server_info["server"]
        
        print(f"🔧 VPN接続を作成中: {vpn_name}")
        print(f"   サーバー: {server}")
        print(f"   IP: {server_info['ip']}")
        
        try:
            # 既存の接続を削除
            subprocess.run([
                "scutil", "--nc", "remove", vpn_name
            ], capture_output=True)
            
            # システム設定でVPN接続を作成するためのコマンド
            # 注意: macOSでは手動設定が必要な場合があります
            print(f"📋 手動でVPN設定を行ってください:")
            print(f"1. システム設定 → ネットワーク")
            print(f"2. '+' をクリックして新しい接続を追加")
            print(f"3. インターフェース: VPN")
            print(f"4. VPNタイプ: L2TP over IPsec")
            print(f"5. 設定:")
            print(f"   - サーバーアドレス: {server}")
            print(f"   - アカウント名: {self.vpn_user}")
            print(f"   - パスワード: {self.vpn_pass}")
            print(f"   - 共有シークレット: {self.vpn_secret}")
            print()
            
            return True
            
        except Exception as e:
            print(f"❌ VPN接続作成エラー: {e}")
            return False
    
    def connect_to_japan_vpn(self, server_info):
        """日本VPNに接続"""
        vpn_name = server_info["name"]
        
        print(f"🌐 日本VPNに接続中: {vpn_name}")
        
        try:
            result = subprocess.run([
                "scutil", "--nc", "start", vpn_name,
                "--user", self.vpn_user,
                "--password", self.vpn_pass,
                "--secret", self.vpn_secret
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
        print("🚀 VPN Gate 動的サーバー取得・記事生成開始")
        print("=" * 60)
        
        # 現在の国を確認
        current_country = self.get_current_country()
        print(f"📍 現在の国: {current_country}")
        
        if current_country == 'JP':
            print("✅ 既に日本からの接続です。記事生成を開始します。")
            return self._run_article_generation(news_file)
        
        # 日本サーバー情報を取得
        japan_servers = self.fetch_japan_servers()
        
        if not japan_servers:
            print("❌ 日本サーバーが見つかりません")
            return False
        
        # 各サーバーを試行
        for i, server_info in enumerate(japan_servers[:3], 1):  # 上位3つを試行
            print(f"\n🔄 VPNサーバー {i}/{min(3, len(japan_servers))} を試行中...")
            print(f"   サーバー: {server_info['server']}")
            print(f"   IP: {server_info['ip']}")
            
            # VPN接続を試行
            if self.connect_to_japan_vpn(server_info):
                # 記事生成
                print(f"\n📝 記事生成開始（{server_info['name']}経由）...")
                success = self._run_article_generation(news_file)
                
                if success:
                    print("✅ 記事生成完了")
                    return True
                else:
                    print("❌ 記事生成失敗")
            else:
                print(f"❌ VPN接続失敗: {server_info['name']}")
        
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
        print("使用方法: python vpngate_dynamic.py <news_file>")
        print("例: python vpngate_dynamic.py daily-articles/rss_news_2025-10-30_06-12-39.json")
        sys.exit(1)
    
    news_file = sys.argv[1]
    
    if not os.path.exists(news_file):
        print(f"❌ ファイルが見つかりません: {news_file}")
        sys.exit(1)
    
    generator = VPNGateDynamicGenerator()
    success = generator.generate_article_with_vpngate(news_file)
    
    if success:
        print("\n🎉 記事生成が正常に完了しました")
        sys.exit(0)
    else:
        print("\n💥 記事生成に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()
