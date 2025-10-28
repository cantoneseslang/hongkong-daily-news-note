#!/usr/bin/env python3
"""
Claude APIのテストスクリプト
"""

import requests
import json

# 設定ファイルから読み込み
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

def test_claude_translation():
    """Claude APIで翻訳テスト"""
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CONFIG["claude_api"]["api_key"],
        "anthropic-version": "2023-06-01"
    }
    
    # Claude API エンドポイント
    api_url = CONFIG["claude_api"]["api_url"]
    
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1000,
        "system": "あなたは香港のニュースを日本語に翻訳する専門家です。中国語・広東語を完全に日本語に翻訳してください。",
        "messages": [
            {
                "role": "user",
                "content": "以下を日本語に翻訳してください：\n\n基孔肯雅熱疫情從佛山爆發，本港繼多宗輸入個案後，10月下旬出現首宗本地個案。"
            }
        ]
    }
    
    print("📤 Claude APIにテストリクエスト送信中...")
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['content'][0]['text']
            print("\n✅ 翻訳結果:")
            print(content)
        else:
            print(f"\n❌ エラー: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ エラー: {e}")

if __name__ == "__main__":
    test_claude_translation()

