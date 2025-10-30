#!/usr/bin/env python3
"""
VPN自動接続付き記事生成スクリプト
記事生成時にVPNを自動接続し、完了後に切断
"""

import subprocess
import sys
import time
import json
import os
from datetime import datetime, timedelta, timezone

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class AutoVPNArticleGenerator:
    def __init__(self):
        self.vpn_name = "Japan VPN 2"  # システムの実際の接続名
        self.vpn_server = "public-vpn-186.opengw.net"
        self.vpn_user = "vpn"
        self.vpn_pass = "vpn"
        self.vpn_secret = "vpn"
        
    def setup_vpn(self):
        """VPN設定を確認（既存設定を使用）"""
        print("🔧 VPN設定を確認中...")
        
        try:
            # 既存のVPN接続を確認
            result = subprocess.run([
                "scutil", "--nc", "list"
            ], capture_output=True, text=True)
            
            if self.vpn_name in result.stdout:
                print("✅ VPN設定が見つかりました")
                return True
            else:
                print("⚠️  VPN設定が見つかりません。手動設定が必要です。")
                print(f"   設定名: {self.vpn_name}")
                print(f"   サーバー: {self.vpn_server}")
                print(f"   ユーザー: {self.vpn_user}")
                print(f"   パスワード: {self.vpn_pass}")
                print(f"   共有シークレット: {self.vpn_secret}")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"⚠️  VPN設定確認エラー: {e}")
            return False
    
    def connect_vpn(self):
        """VPN接続（sudoなし）"""
        print("🌐 VPN接続中...")
        
        try:
            # sudoなしでVPN接続を試行
            result = subprocess.run([
                "scutil", "--nc", "start", self.vpn_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ VPN接続コマンド実行成功")
            else:
                print(f"⚠️  VPN接続コマンドエラー: {result.stderr}")
            
            # 接続完了まで待機
            for i in range(30):  # 最大30秒待機
                time.sleep(1)
                if self.check_vpn_connection():
                    print("✅ VPN接続成功")
                    return True
                print(f"   接続待機中... ({i+1}/30)")
            
            print("❌ VPN接続タイムアウト")
            return False
            
        except Exception as e:
            print(f"❌ VPN接続エラー: {e}")
            return False
    
    def disconnect_vpn(self):
        """VPN切断（sudoなし）"""
        print("🔌 VPN切断中...")
        
        try:
            result = subprocess.run([
                "scutil", "--nc", "stop", self.vpn_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ VPN切断コマンド実行成功")
            else:
                print(f"⚠️  VPN切断コマンドエラー: {result.stderr}")
            
            # 切断完了まで待機
            for i in range(10):  # 最大10秒待機
                time.sleep(1)
                if not self.check_vpn_connection():
                    print("✅ VPN切断完了")
                    return True
                print(f"   切断待機中... ({i+1}/10)")
            
            print("⚠️  VPN切断タイムアウト")
            return True  # 切断は強制的に成功とする
            
        except Exception as e:
            print(f"⚠️  VPN切断エラー: {e}")
            return True  # 切断エラーは無視
    
    def check_vpn_connection(self):
        """VPN接続状態確認"""
        try:
            result = subprocess.run([
                "curl", "-s", "--max-time", "5", "https://ipinfo.io/json"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                country = data.get('country', '')
                return country == 'JP'  # 日本からの接続かチェック
            
        except:
            pass
        
        return False
    
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
    
    def generate_article_with_vpn(self, news_file):
        """VPN接続して記事生成"""
        print("=" * 60)
        print("🚀 VPN自動接続付き記事生成開始")
        print("=" * 60)
        
        # 現在の国を確認
        current_country = self.get_current_country()
        print(f"📍 現在の国: {current_country}")
        
        vpn_connected = False
        
        try:
            # VPN設定確認
            vpn_configured = self.setup_vpn()
            if not vpn_configured:
                print("⚠️  VPN設定が見つかりません。手動設定後、再実行してください。")
                return False
            
            # VPN接続
            if current_country != 'JP':
                if not self.connect_vpn():
                    print("❌ VPN接続に失敗しました")
                    return False
                vpn_connected = True
            else:
                print("✅ 既に日本からの接続です")
            
            # 記事生成
            print("\n📝 記事生成開始...")
            result = subprocess.run([
                "python", "generate_article.py", news_file
            ], cwd=os.getcwd())
            
            if result.returncode == 0:
                print("✅ 記事生成完了")
                return True
            else:
                print("❌ 記事生成失敗")
                return False
                
        except Exception as e:
            print(f"❌ エラー発生: {e}")
            return False
            
        finally:
            # VPN切断
            if vpn_connected:
                self.disconnect_vpn()
            
            print("=" * 60)
            print("🏁 VPN自動接続付き記事生成終了")
            print("=" * 60)

def main():
    if len(sys.argv) != 2:
        print("使用方法: python auto_vpn_generate.py <news_file>")
        print("例: python auto_vpn_generate.py daily-articles/rss_news_2025-10-28_09-37-28.json")
        sys.exit(1)
    
    news_file = sys.argv[1]
    
    if not os.path.exists(news_file):
        print(f"❌ ファイルが見つかりません: {news_file}")
        sys.exit(1)
    
    generator = AutoVPNArticleGenerator()
    success = generator.generate_article_with_vpn(news_file)
    
    if success:
        print("🎉 記事生成が正常に完了しました")
        sys.exit(0)
    else:
        print("💥 記事生成に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()
