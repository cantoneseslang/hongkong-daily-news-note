#!/usr/bin/env python3
"""
ハイブリッド型ニュース取得
1. スクレイピング（メイン）：200〜500件
2. RSS（補助）：既存フィード
3. API（補助）：有料API
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import traceback

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

def main():
    print("\n" + "=" * 80)
    print("🚀 ハイブリッド型ニュース取得開始")
    print("=" * 80)
    
    all_news = []
    
    # 1️⃣ スクレイピング（最優先）
    print("\n📰 Phase 1: Webスクレイピング")
    print("-" * 80)
    try:
        from scrape_news_list import NewsListScraper
        scraper = NewsListScraper()
        scraped_news = scraper.fetch_all_news()
        all_news.extend(scraped_news)
        print(f"✅ スクレイピング: {len(scraped_news)}件取得")
    except Exception as e:
        print(f"⚠️  スクレイピング失敗: {e}")
        traceback.print_exc()
    
    # 2️⃣ RSS（補助）
    print("\n📡 Phase 2: RSSフィード")
    print("-" * 80)
    try:
        from fetch_rss_news import RSSNewsAPI
        rss_api = RSSNewsAPI()
        
        # 既存のprocessed_urlsを一時的にクリアして取得数を増やす
        # （スクレイピングで取得できなかった記事を補完）
        rss_news = rss_api.fetch_all_rss()
        
        # 重複除去しながら追加
        existing_urls = {n.get('url', '').split('?')[0] for n in all_news}
        for news in rss_news:
            url = news.get('url', '').split('?')[0]
            if url not in existing_urls:
                all_news.append(news)
                existing_urls.add(url)
        
        print(f"✅ RSS: {len(rss_news)}件取得（重複除外後: {len(all_news) - len(scraped_news)}件追加）")
    except Exception as e:
        print(f"⚠️  RSS取得失敗: {e}")
        traceback.print_exc()
    
    # 3️⃣ 有料API（さらに補助）
    print("\n🔑 Phase 3: 有料API（補助）")
    print("-" * 80)
    try:
        import os
        if os.path.exists('config.json'):
            from fetch_hongkong_news import HongKongNewsAPI
            api = HongKongNewsAPI()
            api_news = api.fetch_all_news()
            
            # 重複除去しながら追加
            existing_urls = {n.get('url', '').split('?')[0] for n in all_news}
            api_added = 0
            for news in api_news:
                url = news.get('url', '').split('?')[0]
                if url not in existing_urls:
                    all_news.append(news)
                    existing_urls.add(url)
                    api_added += 1
            
            print(f"✅ API: {len(api_news)}件取得（重複除外後: {api_added}件追加）")
        else:
            print("ℹ️  config.json が見つかりません。API取得をスキップします。")
    except Exception as e:
        print(f"⚠️  API取得失敗: {e}")
        traceback.print_exc()
    
    # 統計情報
    print("\n" + "=" * 80)
    print(f"📊 合計取得数: {len(all_news)}件")
    print("=" * 80)
    
    # ソース別統計
    sources = {}
    for news in all_news:
        source = news.get('source', 'Unknown')
        sources[source] = sources.get(source, 0) + 1
    
    print("\n📈 ソース別統計:")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source:20s}: {count:3d}件")
    
    # 保存
    if all_news:
        output_file = f'daily-articles/rss_news_{datetime.now(HKT).strftime("%Y-%m-%d_%H-%M-%S")}.json'
        
        output_data = {
            'fetch_time': datetime.now(HKT).isoformat(),
            'total_count': len(all_news),
            'news': all_news
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 保存完了: {output_file}")
        print("=" * 80)
        return 0
    else:
        print("\n❌ ニュースが取得できませんでした")
        return 1

if __name__ == "__main__":
    sys.exit(main())

