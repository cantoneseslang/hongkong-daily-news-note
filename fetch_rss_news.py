#!/usr/bin/env python3
"""
RSSフィードから香港ニュースを取得
"""

import feedparser
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set
import time
import json
import re
from dateutil import parser as date_parser

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

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
            # 'google_news_hk': 'http://news.google.com.hk/news?pz=1&cf=all&ned=hk&hl=zh-TW&output=rss',  # ← 世界ニュースが混入するため無効化
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
    
    def _is_hk_related(self, title: str, description: str, url: str, source_name: str = "") -> bool:
        """香港関連かを厳格判定（タイトル/説明/URL/ソース）"""
        text = f"{title} {description}".lower()
        url_l = (url or "").lower()
        source_l = (source_name or "").lower()

        # 強い肯定条件
        positive = [
            'hong kong', 'hongkong', '香港', 'kowloon', '九龍', '新界', '香港特別行政區', 'hksar',
            'tsim sha tsui', '尖沙咀', 'wan chai', '灣仔', 'central', '中環', 'mong kok', '旺角',
            'rthk', 'hk01', 'hket', 'scmp', 'the standard', 'chinadaily', 'now新聞', 'now news',
            'hong kong observatory', '香港天文台', 'hkex', '香港交易所', 'mtr', '港鐵'
        ]
        if any(p in text for p in positive):
            return True

        # URLでの肯定（ドメイン・パス）
        url_positive = [
            '/hong-kong', '/hongkong', '/news/hong-kong', '/category/hong-kong',
            '.hk/', '.hk?', '.hk#'
        ]
        if any(u in url_l for u in url_positive):
            return True

        # 粤港澳大湾区・広東省（深圳/東莞/広州/珠海/佛山/惠州/中山 等）を香港圏として許可
        gba_terms = [
            'greater bay area', 'gba', '粵港澳大灣區', '粤港澳大湾区', '大湾区', '珠三角',
            'guangdong', 'shenzhen', 'dongguan', 'guangzhou', 'foshan', 'zhuhai', 'huizhou', 'zhongshan', 'jiangmen', 'zhaoqing',
            '深圳', '深セン', '东莞', '東莞', '广州', '広州', '珠海', '佛山', '惠州', '中山', '江門', '江门', '肇慶', '肇庆'
        ]
        if any(t in text for t in gba_terms) or any(seg in url_l for seg in ['/greater-bay-area', '/gba/']):
            return True

        # SCMPはBusiness/Lifestyleなど世界記事が混ざるため、URLで香港パス必須
        if 'scmp' in source_l or 'scmp.com' in url_l:
            return ('/hong-kong' in url_l) or ('/hongkong' in url_l) or ('/news/hong-kong' in url_l)

        # Yahoo HKは世界記事が混ざるため、URLだけでは許可しない（本文/タイトルに香港系語が必要）
        if 'yahoo' in url_l and 'hk.news.yahoo.com' in url_l:
            return any(p in text for p in positive) or any(u in url_l for u in url_positive)

        return False

    def _load_processed_urls(self) -> Dict[str, str]:
        """処理済みURLを読み込み（URL → ISO日時）"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                urls = data.get('urls', {})
                if isinstance(urls, dict):
                    return {self._normalize_url(k): v for k, v in urls.items()}
                elif isinstance(urls, list):
                    timestamp = data.get('last_updated') or datetime.now(HKT).isoformat()
                    return {self._normalize_url(u): timestamp for u in urls if u}
                else:
                    return {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"⚠️  履歴ファイル読み込みエラー: {e}")
            return {}
    
    def _save_processed_urls(self):
        """処理済みURLを保存"""
        try:
            cutoff_date = datetime.now(HKT) - timedelta(days=60)
            pruned = {}
            for url, ts in self.processed_urls.items():
                try:
                    ts_dt = date_parser.parse(ts)
                except Exception:
                    ts_dt = datetime.now(HKT)
                if ts_dt.replace(tzinfo=HKT) >= cutoff_date:
                    pruned[url] = ts_dt.isoformat()
            self.processed_urls = pruned
            data = {
                'last_updated': datetime.now(HKT).isoformat(),
                'urls': pruned
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  履歴ファイル保存エラー: {e}")

    def _mark_url_as_processed(self, url: str):
        normalized = self._normalize_url(url)
        if not normalized:
            return
        self.processed_urls[normalized] = datetime.now(HKT).isoformat()

    def _has_been_processed(self, url: str) -> bool:
        normalized = self._normalize_url(url)
        return normalized in self.processed_urls

    def _is_url_too_old(self, url: str, max_age_years: int = 2) -> bool:
        if not url:
            return False
        match = re.search(r'(20\d{2})', url)
        if match:
            try:
                year = int(match.group(1))
                current_year = datetime.now(HKT).year
                return year < current_year - max_age_years
            except ValueError:
                return False
        return False
    
    def _is_today_news(self, published_at: str) -> bool:
        """ニュースが過去24時間以内のものかチェック（重複防止のため24時間に戻す）"""
        if not published_at:
            return True  # 日付不明は含める
        
        try:
            pub_date = date_parser.parse(published_at)
            now = datetime.now(HKT)
            
            # 過去24時間以内のニュースのみを含める（48時間だと同じニュースが2日続けて取得される）
            time_diff = now - pub_date.replace(tzinfo=None)
            return time_diff.total_seconds() <= 24 * 3600
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
            # 感染症関連（詳細記事は不要）
            '基孔肯雅熱', 'chikungunya', '登革熱', 'dengue', '疫情', 'epidemic',
            '確診', 'confirmed case', '輸入個案', '本地感染', 'local infection',
            # 政治関連（不要）
            '47人', '47 persons', '47 activists', 'democracy trial',
            '刑期満了', 'prison term', 'sentence completion', 'prison release',
            '民主派', 'democratic', 'democrats', 'pro-democracy',
            '立法会選挙', 'legislative council election', 'legco election',
            '国家安全公署', 'national security office', 'nsa', 'nsf', 'national security law',
            '国安法', '国家安全法', 'national security', '国安公署',
            # 政治犯罪関連（英語）
            'jailed', 'prison', 'sentenced', 'conspiracy', 'overthrow', 'subversion',
            '2019 protest', 'pro-democracy activist', 'political prisoner',
            # 広告・宣伝記事関連
            'presented', 'sponsored', 'advertisement', 'advertorial', 'promotional',
            '広告パートナー', '広告記事', 'スポンサー記事', 'PR記事', 'presented news',
            'building stronger communities through sports'  # 具体的な広告記事タイトル
        ]
        # 採用・募集（求人/職缺/招聘/徵才）系は除外
        recruit_keywords = [
            'recruit', 'recruiting', 'recruitment', 'hiring', 'we are hiring', 'career', 'job opening', 'vacancies', 'vacancy',
            '募集', '求人', '採用', '人材募集', '職種募集', 'キャリア', '採用情報', '採用のお知らせ',
            '招聘', '招聘啟事', '職位空缺', '職缺', '徵才', '招募', '招賢納士'
        ]
        
        for keyword in forbidden_keywords + recruit_keywords:
            if keyword.lower() in text:
                return True
        
        # 香港無関係の国際ニュース（タイトルで判定）
        non_hk_keywords = [
            'gaza', 'israel', 'hamas', 'rafah', 'palestine',
            'iran', 'ukraine', 'russia', 'zelensky',
            'brazil', 'ecuador', 'kenya', 'afghanistan',
            'british', 'prince andrew', 'david attenborough',
            'myanmar', 'starlink',
            'cuba', 'haiti', 'jamaica', 'hurricane', 'melissa',
            'cote d\'ivoire', 'ivory coast', 'wattara', 'ouattara',
            'rio de janeiro', 'drug', 'cartel', 'operation',
            '加薩', '以色列', '哈瑪斯', '巴勒斯坦',
            '烏克蘭', '俄羅斯', '澤連斯基',
            '金鐘獎', '陳偉霆', '台灣',
            'golden horse', 'taiwan election',
            'sudan', 'khartoum', '喀土穆', 'スーダン',
            'trump', 'oracle', 'amazon', 'exxonmobil',
            'トランプ', '米国ビジネス', '米中',
            'キューバ', 'ハイチ', 'ジャマイカ', 'ハリケーン',
            'コートジボワール', 'ブラジル', 'リオデジャネイロ'
        ]
        
        # 香港関連キーワードをチェック（2024-2025年最新版）
        hk_keywords = [
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
            'hong kong free press', 'hk01', 'now news', 'now新聞',
            
            # その他香港関連
            'hong kong dollar', 'hkd', 'hong kong identity card', '香港身份證',
            'hong kong passport', '香港護照', 'hong kong dollar', '港幣',
            'hong kong housing authority', '香港房屋委員會', 'hong kong housing society', '香港房屋協會'
        ]
        has_hk = any(k in text for k in hk_keywords)
        
        if not has_hk:
            # 香港キーワードがない場合、国際ニュースキーワードをチェック
            for keyword in non_hk_keywords:
                if keyword in title.lower():
                    return True
        
        return False
    
    def _normalize_url(self, url: str) -> str:
        """URLを正規化（クエリパラメータを除去してベースURLのみ抽出）"""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            # クエリパラメータとフラグメントを除去
            normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
            return normalized
        except:
            return url
    
    def _is_duplicate_content(self, title: str, existing_titles: List[str]) -> bool:
        """タイトルの類似度をチェックして重複コンテンツかどうか判定（改善版）"""
        import re
        
        def normalize_title(t):
            # タイトルを正規化（小文字化、記号除去、単語分割）
            t = t.lower()
            t = re.sub(r'[^\w\s]', '', t)
            return set(t.split())
        
        title_words = normalize_title(title)
        
        if not title_words:
            return False
        
        for existing in existing_titles:
            existing_words = normalize_title(existing)
            
            if not existing_words:
                continue
            
            common_words = title_words & existing_words
            shortest_len = min(len(title_words), len(existing_words))
            
            if shortest_len <= 4:
                min_common = max(2, shortest_len)
            else:
                min_common = 2
            
            if len(common_words) < min_common:
                continue
            
            all_words = title_words | existing_words
            similarity = len(common_words) / len(all_words) if all_words else 0.0
            coverage = len(common_words) / shortest_len if shortest_len else 0.0
            
            if similarity >= 0.5 and coverage >= 0.6:
                return True
        
        return False
    
    def fetch_scmp_rss(self) -> List[Dict]:
        """SCMP（South China Morning Post）のRSSを取得"""
        print("📰 SCMP RSS からニュース取得中...")
        try:
            feed = feedparser.parse(self.rss_feeds['scmp_hongkong'])
            news_list = []
            filtered_count = 0
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                # 香港関連の厳格判定
                if not self._is_hk_related(title, description, url, 'SCMP'):
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
                self._mark_url_as_processed(url)
            
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
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                if not self._is_hk_related(title, description, url, 'RTHK'):
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
                
                self._mark_url_as_processed(url)
            
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
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                if not self._is_hk_related(title, description, url, 'Yahoo News HK'):
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
                self._mark_url_as_processed(url)
            
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
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                if not self._is_hk_related(title, description, url, 'Google News HK'):
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
                self._mark_url_as_processed(url)
            
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
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                if not self._is_hk_related(title, description, url, 'China Daily HK'):
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
                self._mark_url_as_processed(url)
            
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
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                if not self._is_hk_related(title, description, url, 'Hong Kong Free Press'):
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
                self._mark_url_as_processed(url)
            
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
                
                for entry in feed.entries[:100]:  # 50 → 100に増加
                    url = entry.get('link', '')
                    if self._has_been_processed(url):
                        filtered_count += 1
                        continue
                    if self._is_url_too_old(url):
                        filtered_count += 1
                        self._mark_url_as_processed(url)
                        continue
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

                    if not self._is_hk_related(title, description, url, 'HKET'):
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
                    self._mark_url_as_processed(url)
                
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
            
            for entry in feed.entries[:100]:  # 50 → 100に増加
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
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

                if not self._is_hk_related(title, description, url, source_name):
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
                self._mark_url_as_processed(url)
            
            print(f"  ✅ {len(news_list)}件取得（{filtered_count}件フィルタ済み）")
            return news_list
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def fetch_all_rss(self) -> List[Dict]:
        """全RSSフィードからニュース取得（スクレイピングも含む）"""
        print("\n🚀 ニュース取得開始（RSS + スクレイピング）")
        print("=" * 60)
        
        all_news = []
        existing_titles = []
        existing_urls = set(self.processed_urls.keys())  # 正規化されたURLのセット
        duplicate_count = 0
        url_duplicate_count = 0
        title_duplicate_count = 0
        
        # Phase 1: スクレイピング（優先）
        print("\n📰 Phase 1: Webスクレイピング")
        print("-" * 60)
        try:
            from scrape_news_list import NewsListScraper
            scraper = NewsListScraper()
            scraped_news = scraper.fetch_all_news()
            
            # スクレイピング結果を追加
            scraped_filtered = {
                'total': len(scraped_news),
                'duplicate_url': 0,
                'duplicate_title': 0,
                'old_date': 0,
                'forbidden': 0,
                'non_hk': 0,
                'added': 0
            }
            
            for news in scraped_news:
                url = news.get('url', '')
                title = news.get('title', '')
                if not title or len(title) < 5:
                    continue
                
                normalized_url = self._normalize_url(url)
                
                # 重複チェック
                if normalized_url and normalized_url in existing_urls:
                    scraped_filtered['duplicate_url'] += 1
                    continue
                if self._is_duplicate_content(title, existing_titles):
                    scraped_filtered['duplicate_title'] += 1
                    continue
                
                # 日付フィルタリング（スクレイピングは日付が不明な場合が多いので緩和）
                published_at = news.get('published_at', '')
                if published_at:
                    if not self._is_today_news(published_at):
                        scraped_filtered['old_date'] += 1
                        continue
                # 日付が不明な場合は今日のニュースとして扱う
                
                # 禁止コンテンツフィルタリング
                description = news.get('description', title)
                if self._is_forbidden_content(title, description):
                    scraped_filtered['forbidden'] += 1
                    continue
                
                # 香港関連度チェック
                if not self._is_hk_related(title, description, url, news.get('source', '')):
                    scraped_filtered['non_hk'] += 1
                    continue
                
                all_news.append({
                    'title': title,
                    'description': description,
                    'url': url,
                    'published_at': published_at or datetime.now(HKT).isoformat(),
                    'source': news.get('source', 'Scraped'),
                    'api_source': 'web_scraping'
                })
                existing_urls.add(normalized_url)
                existing_titles.append(title)
                scraped_filtered['added'] += 1
            
            print(f"✅ スクレイピング: {scraped_filtered['total']}件取得")
            print(f"   - 追加: {scraped_filtered['added']}件")
            print(f"   - 除外: 重複URL={scraped_filtered['duplicate_url']}, 重複タイトル={scraped_filtered['duplicate_title']}, 古い日付={scraped_filtered['old_date']}, 禁止={scraped_filtered['forbidden']}, 香港無関係={scraped_filtered['non_hk']}")
        except ImportError as e:
            print(f"⚠️  スクレイピングモジュールが見つかりません: {e}")
            print("   RSSフィードのみで続行します...")
        except Exception as e:
            print(f"⚠️  スクレイピング失敗: {e}")
            import traceback
            traceback.print_exc()
            print("   RSSフィードのみで続行します...")
        
        # Phase 2: RSSフィード（補完）
        print("\n📡 Phase 2: RSSフィード")
        print("-" * 60)
        
        # 各RSSから取得（既存の関数）
        feeds_to_fetch = [
            (self.fetch_scmp_rss, None, None),
            (self.fetch_generic_rss, 'scmp_business', 'SCMP Business'),
            (self.fetch_generic_rss, 'scmp_lifestyle', 'SCMP Lifestyle'),
            (self.fetch_rthk_rss, None, None),
            (self.fetch_generic_rss, 'rthk_business', 'RTHK Business'),
            (self.fetch_yahoo_rss, None, None),
            # (self.fetch_google_news_rss, None, None),  # ← 世界ニュースが混入するため無効化
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
                url = news.get('url', '')
                title = news.get('title', '')
                
                # URL重複チェック（正規化後のURLで比較）
                normalized_url = self._normalize_url(url)
                if normalized_url and normalized_url in existing_urls:
                    url_duplicate_count += 1
                    duplicate_count += 1
                    continue
                
                # タイトル類似度チェック
                if self._is_duplicate_content(title, existing_titles):
                    title_duplicate_count += 1
                    duplicate_count += 1
                    continue
                
                # 重複なしの場合、リストに追加
                all_news.append(news)
                existing_titles.append(title)
                if normalized_url:
                    existing_urls.add(normalized_url)
            
            time.sleep(0.5)  # 1秒 → 0.5秒に短縮
        
        # 処理済みURLを保存
        self._save_processed_urls()
        
        print("=" * 60)
        print(f"✅ 合計 {len(all_news)}件のニュースを取得")
        print(f"🔄 重複除外: {duplicate_count}件（URL重複: {url_duplicate_count}件、タイトル類似: {title_duplicate_count}件）")
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
        
        timestamp = datetime.now(HKT).strftime('%Y-%m-%d_%H-%M-%S')
        output_path = f"daily-articles/rss_news_{timestamp}.json"
        
        data = {
            'fetch_time': datetime.now(HKT).isoformat(),
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
