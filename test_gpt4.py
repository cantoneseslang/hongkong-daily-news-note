#!/usr/bin/env python3
"""
OpenAI GPT-4のテストスクリプト
"""

import requests
import json

# 設定ファイルから読み込み
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

def test_gpt4_translation():
    """GPT-4で翻訳テスト"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CONFIG['openai_api']['api_key']}"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "あなたは香港のニュースを日本語に翻訳する専門家です。中国語・広東語を完全に日本語に翻訳してください。"
            },
            {
                "role": "user",
                "content": "以下を日本語に翻訳してください：\n\n基孔肯雅熱疫情從佛山爆發，本港繼多宗輸入個案後，10月下旬出現首宗本地個案。"
            }
        ],
        "temperature": 0.1
    }
    
    print("📤 OpenAI GPT-4にテストリクエスト送信中...")
    
    try:
        response = requests.post(
            CONFIG['openai_api']['api_url'],
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print("\n✅ 翻訳結果:")
            print(content)
        else:
            print(f"\n❌ エラー: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ エラー: {e}")

if __name__ == "__main__":
    test_gpt4_translation()

