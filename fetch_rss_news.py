#!/usr/bin/env python3
"""
RSSフィードから香港ニュースを取得
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Set
import time
import json
from dateutil import parser as date_parser

class RSSNewsAPI:
    def __init__(self, history_file: str = 'daily-articles/processed_urls.json'):
        self.rss_feeds = {
            # 総合ニュース
            'scmp_hongkong': 'https://www.scmp.com/rss/2/feed',
            'scmp_business': 'https://www.scmp.com/rss/5/feed',  # ビジネス
            'scmp_lifestyle': 'https://www.scmp.com/rss/322184/feed',  # ライフスタイル
            'rthk_news': 'https://rthk.hk/rthk/news/rss/e_expressnews_elocal.xml',
            'rthk_business': 'https://rthk.hk/rthk/news/rss/e_expressnews_ebusiness.xml',  # ビジネス
            'yahoo_hk': 'http://hk.news.yahoo.com/rss/hong-kong',
            'google_news_hk': 'http://news.google.com.hk/news?pz=1&cf=all&ned=hk&hl=zh-TW&output=rss',
            'chinadaily_hk': 'http://www.chinadaily.com.cn/rss/hk_rss.xml',
            'hkfp': 'https://www.hongkongfp.com/feed/',
            'hket_hk': 'https://www.hket.com/rss/hongkong',
            'hket_finance': 'https://www.hket.com/rss/finance',  # 財経
            'hket_property': 'https://www.hket.com/rss/property',  # 不動産
        }
        self.weather_feeds = {
            'weather_warning': 'https://rss.weather.gov.hk/rss/WeatherWarningSummaryv2_uc.xml',
            'weather_forecast': 'https://rss.weather.gov.hk/rss/LocalWeatherForecast_uc.xml',
            'current_weather': 'https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml',
            'nine_day_forecast': 'https://rss.weather.gov.hk/rss/SeveralDaysWeatherForecast_uc.xml',
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.history_file = history_file
        self.processed_urls = self._load_processed_urls()
    
    def _load_processed_urls(self) -> Set[str]:
        """処理済みURLを読み込み"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('urls', []))
        except FileNotFoundError:
            return set()
        except Exception as e:
            print(f"⚠️  履歴ファイル読み込みエラー: {e}")
            return set()
    
    def _save_processed_urls(self):
        """処理済みURLを保存"""
        try:
            # 最近30日分のみ保持（メモリ節約）
            cutoff_date = datetime.now() - timedelta(days=30)
            
            data = {
                'last_updated': datetime.now().isoformat(),
                'urls': list(self.processed_urls)
            }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  履歴ファイル保存エラー: {e}")
    
    def _is_today_news(self, published_at: str) -> bool:
        """ニュースが過去24時間以内のものかチェック"""
        if not published_at:
            return True  # 日付不明は含める
        
        try:
            pub_date = date_parser.parse(published_at)
            now = datetime.now()
            
            # 過去48時間以内のニュースを含める（より多様なニュースを収集）
            time_diff = now - pub_date.replace(tzinfo=None)
            return time_diff.total_seconds() <= 48 * 3600
        except:
            return True  # パース失敗は含める
    
    def _is_forbidden_content(self, title: str, description: str) -> bool:
        """禁止コンテンツかチェック"""
        text = (title + ' ' + description).lower()
        
        # 禁止キーワード
        forbidden_keywords = [
            'wwii', 'ww2', 'world war ii', '二次大戦', '抗日', '日本侵略',
            'japanese invasion', 'sino-japanese war', '中日战争', '抗戰',
            'envoys given special tour', 'exhibition on chinese victory',
            # ギャンブル関連
            'horse racing', 'jockey', 'mark six', 'lottery',
            '競馬', '賽馬', '騎師', '六合彩', '賭博', '博彩', 'casino', 'gambling',
            'boat racing', '競艇', 'betting',
            # 政治関連（不要）
            '47人', '47 persons', '47 activists', 'democracy trial',
            '刑期満了', 'prison term', 'sentence completion', 'prison release',
            '民主派', 'democratic', 'democrats', 'pro-democracy',
            '立法会選挙', 'legislative council election', 'legco election',
            '国家安全公署', 'national security office', 'nsa', 'nsf', 'national security law',
            '国安法', '国家安全法', 'national security', '国安公署',
            # 政治犯罪関連（英語）
            'jailed', 'prison', 'sentenced', 'conspiracy', 'overthrow', 'subversion',
            '2019 protest', 'pro-democracy activist', 'political prisoner'
        ]
        
        for keyword in forbidden_keywords:
            if keyword.lower() in text:
                return True
        
        # 香港無関係の国際ニュース（タイトルで判定）
        non_hk_keywords = [
            'gaza', 'israel', 'hamas', 'rafah', 'palestine',
            'iran', 'ukraine', 'russia', 'zelensky',
            'brazil', 'ecuador', 'kenya', 'afghanistan',
            'british', 'prince andrew', 'david attenborough',
            'myanmar', 'starlink',
            '加薩', '以色列', '哈瑪斯', '巴勒斯坦',
            '烏克蘭', '俄羅斯', '澤連斯基',
            '金鐘獎', '陳偉霆', '台灣',
            'golden horse', 'taiwan election',
            'sudan', 'khartoum', '喀土穆', 'スーダン',
            'trump', 'oracle', 'amazon', 'exxonmobil',
            'トランプ', '米国ビジネス', '米中'
        ]
        
        # タイトルのみでチェック（香港関連キーワードがあればOK）
        hk_keywords = ['hong kong', 'hongkong', 'hk', '香港', 'central', 'kowloon', 'wan chai', 'mtr', '港']
        has_hk = any(k in text for k in hk_keywords)
        
        if not has_hk:
            # 香港キーワードがない場合、国際ニュースキーワードをチェック
            for keyword in non_hk_keywords:
                if keyword in title.lower():
                    return True
        
        return False
    
    def _is_duplicate_content(self, title: str, existing_titles: List[str]) -> bool:
        """タイトルの類似度をチェックして重複コンテンツかどうか判定"""
        # タイトルを正規化（小文字化、記号除去）
        def normalize_title(t):
            import re
            t = t.lower()
            # 記号と数字を除去
            t = re.sub(r'[^\w\s]', '', t)
            return set(t.split())
        
        title_words = normalize_title(title)
        
        for existing in existing_titles:
            existing_words = normalize_title(existing)
            
            # 共通単語の数をチェック
            common_words = title_words & existing_words
            
            # 3単語以上共通 かつ 共通率が60%以上なら重複とみなす
            if len(common_words) >= 3:
                similarity = len(common_words) / max(len(title_words), len(existing_words))
                if similarity >= 0.6:
                    return True
        
        return False
    
    def fetch_scmp_rss(self) -> List[Dict]:
        """SCMP（South China Morning Post）のRSSを取得"""
        print("📰 SCMP RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['scmp_hongkong'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': 'SCMP',
                    'api_source': 'rss_scmp'
                })
                
                # 処理済みURLに追加
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_rthk_rss(self) -> List[Dict]:
        """RTHK（Radio Television Hong Kong）のRSSを取得"""
        print("📰 RTHK RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['rthk_news'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': 'RTHK',
                    'api_source': 'rss_rthk'
                })
                
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_yahoo_rss(self) -> List[Dict]:
        """Yahoo News HKのRSSを取得"""
        print("📰 Yahoo News HK RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['yahoo_hk'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': 'Yahoo News HK',
                    'api_source': 'rss_yahoo_hk'
                })
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_google_news_rss(self) -> List[Dict]:
        """Google News HKのRSSを取得"""
        print("📰 Google News HK RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['google_news_hk'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': 'Google News HK',
                    'api_source': 'rss_google_news_hk'
                })
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_chinadaily_rss(self) -> List[Dict]:
        """China Daily HKのRSSを取得"""
        print("📰 China Daily HK RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['chinadaily_hk'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': 'China Daily HK',
                    'api_source': 'rss_chinadaily_hk'
                })
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_hkfp_rss(self) -> List[Dict]:
        """Hong Kong Free PressのRSSを取得"""
        print("📰 Hong Kong Free Press RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['hkfp'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': 'Hong Kong Free Press',
                    'api_source': 'rss_hkfp'
                })
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_hket_rss(self) -> List[Dict]:
        """HKET（香港経済日報）のRSSを取得（User-Agent必要）"""
        print("📰 HKET 香港 RSS からニュース取得中...")
        try:
            response = requests.get(self.rss_feeds['hket_hk'], headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                news_list = []
                filtered_count = 0
                
                for entry in feed.entries[:50]:
                    url = entry.get('link', '')
                    published_at = entry.get('published', entry.get('updated', ''))
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    # 日付フィルタリング
                    if not self._is_today_news(published_at):
                        filtered_count += 1
                        continue
                    
                    # 禁止コンテンツフィルタリング
                    if self._is_forbidden_content(title, description):
                        filtered_count += 1
                        continue
                    
                    news_list.append({
                        'title': title,
                        'description': description,
                        'url': url,
                        'published_at': published_at,
                        'source': 'HKET',
                        'api_source': 'rss_hket'
                    })
                    self.processed_urls.add(url)
                
                print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
                return news_list
            else:
                print(f"  ❌ HTTPエラー: {response.status_code}")
                return []
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_generic_rss(self, feed_key: str, source_name: str, use_headers: bool = False) -> List[Dict]:
        """汎用RSS取得関数"""
        print(f"📰 {source_name} RSS からニュース取得中...")
        try:
            if use_headers:
                response = requests.get(self.rss_feeds[feed_key], headers=self.headers, timeout=5)
                feed = feedparser.parse(response.content)
            else:
                feed = feedparser.parse(self.rss_feeds[feed_key])
            
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                published_at = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue
                
                news_list.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at,
                    'source': source_name,
                    'api_source': feed_key
                })
                self.processed_urls.add(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_all_rss(self) -> List[Dict]:
        """全RSSフィードからニュース取得"""
        print("\n🚀 RSS フィードからニュース取得開始")
        print("=" * 60)
        
        all_news = []
        existing_titles = []
        duplicate_count = 0
        
        # 各RSSから取得（既存の関数）
        feeds_to_fetch = [
            (self.fetch_scmp_rss, None, None),
            (self.fetch_generic_rss, 'scmp_business', 'SCMP Business'),
            (self.fetch_generic_rss, 'scmp_lifestyle', 'SCMP Lifestyle'),
            (self.fetch_rthk_rss, None, None),
            (self.fetch_generic_rss, 'rthk_business', 'RTHK Business'),
            (self.fetch_yahoo_rss, None, None),
            (self.fetch_google_news_rss, None, None),
            (self.fetch_chinadaily_rss, None, None),
            (self.fetch_hkfp_rss, None, None),
            (self.fetch_hket_rss, None, None),
            (self.fetch_generic_rss, 'hket_finance', 'HKET Finance'),
            (self.fetch_generic_rss, 'hket_property', 'HKET Property'),
        ]
        
        for feed_info in feeds_to_fetch:
            func = feed_info[0]
            if feed_info[1] is None:
                # 既存の専用関数
                news_items = func()
            else:
                # 汎用関数
                news_items = func(feed_info[1], feed_info[2], feed_info[1].startswith('hket'))
            
            for news in news_items:
                if not self._is_duplicate_content(news['title'], existing_titles):
                    all_news.append(news)
                    existing_titles.append(news['title'])
                else:
                    duplicate_count += 1
            
            time.sleep(0.5)  # 1秒 → 0.5秒に短縮
        
        # 処理済みURLを保存
        self._save_processed_urls()
        
        print("=" * 60)
        print(f"✅ 合計 {len(all_news)}件のニュースを取得")
        print(f"🔄 重複除外: {duplicate_count}件")
        print(f"📝 処理済みURL総数: {len(self.processed_urls)}件\n")
        
        return all_news
    
    def fetch_weather_info(self) -> Dict:
        """香港天文台の天気情報を取得"""
        print("\n🌤️  天気情報取得開始")
        print("=" * 60)
        
        weather_data = {}
        
        for key, url in self.weather_feeds.items():
            try:
                feed = feedparser.parse(url)
                if len(feed.entries) > 0:
                    entry = feed.entries[0]
                    weather_data[key] = {
                        'title': entry.get('title', ''),
                        'description': entry.get('description', entry.get('summary', '')),
                        'published_at': entry.get('published', entry.get('updated', '')),
                    }
                    print(f"  ✅ {key} 取得完了")
            except Exception as e:
                print(f"  ❌ {key} エラー: {e}")
        
        print("=" * 60)
        print(f"✅ 天気情報 {len(weather_data)}件取得\n")
        
        return weather_data

if __name__ == "__main__":
    import json
    from scrape_article import ArticleScraper
    
    rss_api = RSSNewsAPI()
    news = rss_api.fetch_all_rss()
    weather = rss_api.fetch_weather_info()
    
    if news:
        # 全文取得処理を追加
        print("\n📰 記事全文を取得中...")
        print("=" * 60)
        
        scraper = ArticleScraper()
        enriched_news = []
        
        for i, item in enumerate(news, 1):
            print(f"\n[{i}/{len(news)}] {item['title'][:60]}...")
            
            # URLから全文を取得
            full_content = scraper.scrape_article(item['url'])
            
            if full_content:
                item['full_content'] = full_content
                print(f"    ✅ {len(full_content)}文字取得")
            else:
                # 取得失敗時はdescriptionを使用
                item['full_content'] = item.get('description', '')
                print(f"    ⚠️  全文取得失敗、descriptionを使用")
            
            enriched_news.append(item)
        
        print("\n" + "=" * 60)
        print(f"✅ 全文取得完了: {len(enriched_news)}件\n")
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_path = f"daily-articles/rss_news_{timestamp}.json"
        
        data = {
            'fetch_time': datetime.now().isoformat(),
            'total_count': len(enriched_news),
            'news': enriched_news,
            'weather': weather
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 保存完了: {output_path}")
        
        # サンプル表示
        print("\n📋 取得したニュース（最初の5件）:")
        for i, item in enumerate(enriched_news[:5], 1):
            print(f"\n{i}. {item['title']}")
            print(f"   ソース: {item['source']} ({item['api_source']})")
            print(f"   全文: {len(item.get('full_content', ''))}文字")
        
        if weather:
            print("\n🌤️  天気情報も取得しました")
    else:
        print("\n❌ ニュースを取得できませんでした")
