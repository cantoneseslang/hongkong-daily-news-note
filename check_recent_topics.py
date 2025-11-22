#!/usr/bin/env python3
"""
過去3日間の記事から頻出トピックを抽出
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set
from collections import Counter

HKT = timezone(timedelta(hours=8))

def extract_topics_from_article(file_path: str) -> List[str]:
    """記事ファイルからトピック（主要なキーワード）を抽出"""
    topics = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # トピックキーワードを抽出
        topic_patterns = [
            r'全国運動会|National Games|全運會',
            r'立法会選挙|LegCo election',
            r'施政報告|Policy Address',
            r'失業率|unemployment rate',
            r'GDP|経済成長',
            r'オリンピック|Olympics',
            r'ワールドカップ|World Cup',
            r'台風|Typhoon',
            r'新型コロナ|COVID',
            r'不動産価格|property prices',
        ]
        
        for pattern in topic_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                topics.append(pattern.split('|')[0])  # 最初のキーワードを使用
        
        return topics
    except Exception as e:
        print(f"エラー: {file_path} の読み込み失敗 - {e}")
        return []

def get_recent_topics(days: int = 3) -> Dict[str, int]:
    """過去N日間の頻出トピックを取得"""
    topic_counter = Counter()
    
    today = datetime.now(HKT)
    
    for i in range(1, days + 1):
        target_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        article_file = f'daily-articles/hongkong-news_{target_date}.md'
        
        if os.path.exists(article_file):
            topics = extract_topics_from_article(article_file)
            topic_counter.update(topics)
            print(f"✅ {target_date}: {len(topics)}個のトピック検出")
        else:
            print(f"⏭️  {target_date}: ファイルなし")
    
    return dict(topic_counter)

def is_overused_topic(title: str, description: str, recent_topics: Dict[str, int], threshold: int = 3) -> bool:
    """タイトル/説明が過去N日間で頻出トピックに該当するか"""
    content = f"{title} {description}".lower()
    
    for topic, count in recent_topics.items():
        if count >= threshold:  # 3日間で3回以上出現
            if topic.lower() in content or any(kw in content for kw in topic.split('|')):
                return True
    
    return False

if __name__ == "__main__":
    recent_topics = get_recent_topics(days=3)
    
    print("\n" + "=" * 60)
    print("📊 過去3日間の頻出トピック:")
    print("=" * 60)
    
    for topic, count in sorted(recent_topics.items(), key=lambda x: x[1], reverse=True):
        status = "⚠️ 過剰" if count >= 3 else "✅ 正常"
        print(f"  {status} {topic}: {count}回")


