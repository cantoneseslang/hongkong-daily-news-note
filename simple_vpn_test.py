#!/usr/bin/env python3
"""
簡単なVPNテストスクリプト
"""

import subprocess
import json
import time

def get_current_country():
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

def test_vpn_connection():
    """VPN接続テスト"""
    print("📍 現在の国:", get_current_country())
    
    # VPN接続を試行
    print("🌐 VPN接続を試行中...")
    
    # 利用可能なVPN接続を確認
    result = subprocess.run([
        "scutil", "--nc", "list"
    ], capture_output=True, text=True)
    
    print("利用可能なVPN接続:")
    print(result.stdout)
    
    # 日本VPNを探す
    if "Japan" in result.stdout:
        print("✅ Japan VPNが見つかりました")
        
        # 接続を試行
        connect_result = subprocess.run([
            "scutil", "--nc", "start", "Japan VPN"
        ], capture_output=True, text=True)
        
        print("接続結果:", connect_result.returncode)
        print("エラー:", connect_result.stderr)
        
        # 接続確認
        time.sleep(5)
        print("📍 接続後の国:", get_current_country())
    else:
        print("❌ Japan VPNが見つかりません")

if __name__ == "__main__":
    test_vpn_connection()
