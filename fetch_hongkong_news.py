#!/usr/bin/env python3
"""
香港ニュース取得スクリプト
3つのニュースAPIから並列でニュースを取得し、統合します
"""

import requests
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import time

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class HongKongNewsAPI:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.api_keys = self.config['api_keys']
        self.settings = self.config['settings']
        
    def fetch_newsdata_io(self) -> List[Dict]:
        """NewsData.ioからニュース取得"""
        print("📰 NewsData.io からニュース取得中...")
        url = "https://newsdata.io/api/1/news"
        params = {
            'apikey': self.api_keys['newsdata_io'],
            'country': 'hk',
            'language': 'en',
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                print(f"  ✅ {len(results)}件取得")
                return [{
                    'title': item.get('title'),
                    'description': item.get('description'),
                    'url': item.get('link'),
                    'published_at': item.get('pubDate'),
                    'source': item.get('source_id', 'NewsData.io'),
                    'api_source': 'newsdata_io'
                } for item in results[:10]]
            else:
                print(f"  ❌ エラー: {response.status_code}")
                return []
        except Exception as e:
            print(f"  ❌ 例外: {e}")
            return []
    
    def fetch_world_news_api(self) -> List[Dict]:
        """World News APIからニュース取得"""
        print("📰 World News API からニュース取得中...")
        url = "https://api.worldnewsapi.com/search-news"
        
        yesterday = (datetime.now(HKT) - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now(HKT).strftime('%Y-%m-%d')
        
        params = {
            'api-key': self.api_keys['world_news_api'],
            'source-country': 'hk',
            'language': 'en',
            'earliest-publish-date': yesterday,
            'latest-publish-date': today,
            'number': 10,
            'sort': 'publish-time',
            'sort-direction': 'desc'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news = data.get('news', [])
                print(f"  ✅ {len(news)}件取得")
                return [{
                    'title': item.get('title'),
                    'description': item.get('text', '')[:500],
                    'url': item.get('url'),
                    'published_at': item.get('publish_date'),
                    'source': item.get('source', 'World News API'),
                    'api_source': 'world_news_api'
                } for item in news]
            else:
                print(f"  ❌ エラー: {response.status_code}")
                return []
        except Exception as e:
            print(f"  ❌ 例外: {e}")
            return []
    
    def fetch_news_api(self) -> List[Dict]:
        """News APIからニュース取得"""
        print("📰 News API からニュース取得中...")
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            'apiKey': self.api_keys['news_api'],
            'country': 'hk',
            'pageSize': 10
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                print(f"  ✅ {len(articles)}件取得")
                return [{
                    'title': item.get('title'),
                    'description': item.get('description'),
                    'url': item.get('url'),
                    'published_at': item.get('publishedAt'),
                    'source': item.get('source', {}).get('name', 'News API'),
                    'api_source': 'news_api'
                } for item in articles]
            else:
                print(f"  ❌ エラー: {response.status_code}")
                return []
        except Exception as e:
            print(f"  ❌ 例外: {e}")
            return []
    
    def is_hongkong_related(self, news: Dict) -> bool:
        """ニュースが香港関連かチェック"""
        # Hong Kong Free Pressを除外
        url = news.get('url', '').lower()
        if 'hongkongfp.com' in url:
            return False
        
        keywords = [
            # 基本キーワード
            'hong kong', 'hongkong', 'hk', '香港', '港',
            
            # 主要地区・地名
            'central', 'kowloon', 'wan chai', 'causeway bay', 'tai koo', 'admiralty',
            'tsim sha tsui', 'victoria harbour', 'lantau', 'kwai chung', 'tin shui wai', 
            'tiu keng leng', 'sha tin', 'mong kok', 'yau ma tei', 'jordan', 'tai po',
            '中環', '九龍', '灣仔', '銅鑼灣', '太古', '金鐘', '尖沙咀', '旺角',
            '油麻地', '佐敦', '大埔', '葵涌', '天水圍', '調景嶺', '沙田',
            '維多利亞港', '大嶼山', '青衣', '屯門', '元朗', '上水', '粉嶺',
            
            # 交通・インフラ
            'mtr', '港鐵', 'hong kong international airport', '香港國際機場',
            'hong kong tramways', '香港電車', 'star ferry', '天星小輪',
            'hong kong zhuhai macau bridge', '港珠澳大橋', 'high speed rail', '高鐵',
            
            # 政治・行政（最新）
            'legco', 'legislative council', '立法會', 'hksar', '香港特別行政區',
            'john lee', '李家超', '行政長官', 'chief executive',
            'hong kong government', '香港政府', 'hong kong police', '香港警察',
            'hong kong observatory', '香港天文台', 'hong kong monetary authority', '金管局',
            
            # 経済・金融
            'hkex', 'hong kong stock exchange', '香港交易所', 'hong kong dollar', '港幣',
            'greater bay area', '粵港澳大灣區', 'hong kong finance', '香港金融',
            
            # 文化・観光
            'm+ museum', '西九文化區', 'west kowloon cultural district', 'hong kong disneyland',
            '香港迪士尼', 'ocean park', '海洋公園', 'hong kong arts festival', '香港藝術節',
            'hong kong international film festival', '香港國際電影節',
            
            # 教育・大学
            'university of hong kong', '香港大學', 'chinese university of hong kong', '香港中文大學',
            'hong kong university of science and technology', '香港科技大學',
            'city university of hong kong', '香港城市大學',
            
            # メディア・ニュースソース
            'scmp', 'south china morning post', '南華早報', 'rthk', '香港電台',
            'chinadaily', 'hket', 'the standard', 'ming pao', '明報',
            'hong kong free press', 'hk01', 'now news', 'now新聞'
        ]
        
        text = f"{news.get('title', '')} {news.get('description', '')}".lower()
        
        # 香港関連キーワードが含まれているかチェック
        for keyword in keywords:
            if keyword in text:
                return True
        
        # URLに香港関連ドメインが含まれているかチェック（HKFPは除外済み）
        hk_domains = ['scmp.com', 'thestandard.com.hk', 
                      'rthk.hk', 'chinadailyhk.com', 'hk01.com']
        for domain in hk_domains:
            if domain in url:
                return True
        
        return False
    
    def fetch_all_news(self) -> List[Dict]:
        """3つのAPIから並列でニュース取得"""
        print("\n🚀 香港ニュース取得開始")
        print("=" * 60)
        
        all_news = []
        
        # 並列実行
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.fetch_newsdata_io): 'newsdata_io',
                executor.submit(self.fetch_world_news_api): 'world_news_api',
                executor.submit(self.fetch_news_api): 'news_api'
            }
            
            for future in as_completed(futures):
                api_name = futures[future]
                try:
                    results = future.result()
                    all_news.extend(results)
                except Exception as e:
                    print(f"  ❌ {api_name} でエラー: {e}")
        
        print("=" * 60)
        print(f"✅ 合計 {len(all_news)}件のニュースを取得")
        
        # 重複除去（URLベース）
        seen_urls = set()
        unique_news = []
        for news in all_news:
            if news['url'] and news['url'] not in seen_urls:
                seen_urls.add(news['url'])
                unique_news.append(news)
        
        print(f"📊 重複除去後: {len(unique_news)}件")
        
        # 香港関連のみフィルタリング
        hongkong_news = [news for news in unique_news if self.is_hongkong_related(news)]
        print(f"🇭🇰 香港関連: {len(hongkong_news)}件\n")
        
        return hongkong_news
    
    def save_raw_news(self, news: List[Dict], output_path: str = None):
        """取得したニュースをJSON形式で保存"""
        if output_path is None:
            timestamp = datetime.now(HKT).strftime('%Y-%m-%d_%H-%M-%S')
            output_path = f"daily-articles/raw_news_{timestamp}.json"
        
        data = {
            'fetch_time': datetime.now(HKT).isoformat(),
            'total_count': len(news),
            'news': news
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 ニュースを保存: {output_path}")
        return output_path

if __name__ == "__main__":
    # テスト実行
    api = HongKongNewsAPI()
    news = api.fetch_all_news()
    
    if news:
        saved_path = api.save_raw_news(news)
        print(f"\n✅ 取得完了！")
        print(f"📁 保存先: {saved_path}")
        
        # サンプル表示
        print("\n📋 取得したニュース（最初の3件）:")
        for i, item in enumerate(news[:3], 1):
            print(f"\n{i}. {item['title']}")
            print(f"   ソース: {item['source']} ({item['api_source']})")
            print(f"   URL: {item['url']}")
    else:
        print("\n❌ ニュースを取得できませんでした")

