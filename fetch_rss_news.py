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
import html
import os
from dateutil import parser as date_parser

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))


def _should_run_playwright_news_scrape() -> bool:
    """
    Phase1 の Playwright 一覧スクレイピング（Google News / HK01 / 明報 / am730）。

    - GitHub Actions では既定でオフ（ブラウザ起動・複数ページで 10〜数十分かかるため）。
    - ローカルでは既定オン（従来どおり）。
    - 強制オン: 環境変数 RUN_PLAYWRIGHT_NEWS_SCRAPE=1
    - 強制オフ: SKIP_NEWS_LIST_SCRAPING=1
    """
    if os.environ.get('SKIP_NEWS_LIST_SCRAPING', '').lower() in ('1', 'true', 'yes'):
        return False
    if os.environ.get('RUN_PLAYWRIGHT_NEWS_SCRAPE', '').lower() in ('1', 'true', 'yes'):
        return True
    if os.environ.get('GITHUB_ACTIONS', '').lower() == 'true':
        return False
    return True

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
            'google_news_hk': 'https://news.google.com/rss/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNRE5vTmpRU0JYcG9MVWhMS0FBUAE?hl=zh-HK&gl=HK&ceid=HK:zh-Hant',  # 香港トピック（24時間以内フィルタリング適用）
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

    def _clean_feed_text(self, text: str) -> str:
        """RSS summaryに混ざるHTML残骸や壊れたリンク断片を除去"""
        if not text:
            return ""

        cleaned = html.unescape(text)
        cleaned = re.sub(r'(?is)<br\s*/?>', '\n', cleaned)
        cleaned = re.sub(r'(?is)<a\s+href=["\'][^"\']*["\'][^>]*>(.*?)</a>', r'\1', cleaned)
        cleaned = re.sub(r'(?is)<a\s+href=["\'][^"\']*["\'][^>]*>', ' ', cleaned)
        cleaned = re.sub(r'(?is)<a\s+href=[^>\s]+', ' ', cleaned)
        cleaned = re.sub(r'(?is)</a>', ' ', cleaned)
        cleaned = re.sub(r'(?is)<[^>]+>', ' ', cleaned)

        lines = []
        for raw_line in cleaned.splitlines():
            line = re.sub(r'\s+', ' ', raw_line).strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered in {'google news', 'google news hk'}:
                continue
            if 'comprehensive up-to-date news coverage' in lowered:
                continue
            if '<a href' in lowered or 'href=' in lowered:
                continue
            if re.fullmatch(r'[A-Za-z0-9_/\-+=]{40,}', line):
                continue
            lines.append(line)

        return '\n'.join(lines).strip()
    
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
        
        # HK01の「即時國際」セクションは香港と無関係な国際ニュースが多いため、厳格にチェック
        if 'hk01.com' in url_l and ('即時國際' in url or '/channel/19' in url_l or '即時國際' in url_l):
            # 香港関連キーワードがタイトル/説明に含まれている場合のみ許可
            if not any(p in text for p in positive):
                return False
        
        # HK01の「國際分析」セクションも同様に厳格にチェック
        if 'hk01.com' in url_l and ('國際分析' in url or '國際分析' in url_l):
            if not any(p in text for p in positive):
                return False

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
            # 全運会関連（NGワード）
            '全国運動会', '全運會', '全运会', 'national games', '全運', '全运',
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
            'building stronger communities through sports',  # 具体的な広告記事タイトル
            # 火災関連（宏福苑大火など同じニュースが繰り返し取得されるため除外）
            '宏福苑', 'wang fuk court', 'wang fuk', 'kwong fuk', '大埔大火', '大埔火災', 'tai po fire',
            '宏福苑大火', '宏福苑火災', '大火', 'deadly fire', 'fire-ravaged', 'hong kong fire',
            'fire climbs', 'death toll', 'mourning period', 'fire displaced',
            'fire survivor', 'blaze', 'inferno', '死裡逃生', '受困', '火警',
            '捐款', 'donation', '援助基金', 'relief fund', '受災', 'disaster relief',
            'fire victims', 'fire identification', '身元確認', '追悼期間',
            'fire teaches', 'relief aid', 'relief booth', '救援物資',
            # 性犯罪関連（同じニュースが繰り返し取得されるため除外）
            'sexual crime', '性犯罪', 'consent reform', '同意の新たな基準',
            'reforming hong kong approach sexual crimes', 'new test consent',
            # エアバス関連（重複が多いため一時的に除外）
            'airbus a320', 'エアバスa320', 'a320 software', 'a320型機',
            'emergency grounding', '緊急運航停止', '約6000機',
            '空中巴士', 'airbus', 'a320', '停飛', 'grounding', '客機軟件',
            '香港快運', 'hk express'
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
        # 注意: 香港関連キーワード（港隊、香港チームなど）が含まれている場合は除外しない
        non_hk_keywords = [
            'gaza', 'israel', 'hamas', 'rafah', 'palestine',
            'iran', 'ukraine', 'russia', 'zelensky',
            'brazil', 'ecuador', 'kenya', 'afghanistan',
            'british', 'prince andrew', 'david attenborough',
            'myanmar', 'starlink',
            'cuba', 'haiti', 'jamaica', 'hurricane', 'melissa',
            'cote d\'ivoire', 'ivory coast', 'wattara', 'ouattara',
            'rio de janeiro', 'drug', 'cartel', 'operation',
            '加薩', '以色列', '哈瑪ス', '巴勒斯坦',
            '烏克蘭', '俄羅斯', '澤連斯基',
            '金鐘獎', '陳偉霆', '台灣',
            'golden horse', 'taiwan election',
            'sudan', 'khartoum', '喀土穆', 'スーダン',
            'trump', 'oracle', 'amazon', 'exxonmobil',
            'トランプ', '米国ビジネス', '米中',
            'キューバ', 'ハイチ', 'ジャマイカ', 'ハリケーン',
            'コートジボワール', 'ブラジル', 'リオデジャネイロ',
            # 日本関連（香港と無関係なもの）
            '日本愛知', '愛知縣', 'aichi', '高市早苗', '中日緊張', '中日関係', 'sino-japanese',
            '日本経済', 'japan economy', '日本政治', 'japan politics',
            # シンガポール関連（香港チームが含まれていない場合のみ）
            # 注意: 「港隊」「香港チーム」が含まれている場合は除外しない
            # 中国の国際ニュース（香港と無関係なもの）
            '中國既強烈反擊', '中國正預備日本', '亞洲版烏克蘭'
        ]
        
        # 香港関連キーワードが含まれている場合は除外しない
        hk_related_in_title = any(kw in text for kw in ['港隊', '香港隊', '港隊', 'hong kong team', 'hk team', '香港チーム'])
        if hk_related_in_title:
            return False
        
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
            # Google News のリダイレクトURLを元のURLに変換
            if 'news.google.com/read/' in url or 'news.google.com/rss/articles/' in url:
                # Google News の場合は完全なURLをそのまま使う（パラメータ込み）
                return url.split('?')[0]  # クエリパラメータのみ除去
            
            parsed = urlparse(url)
            # クエリパラメータとフラグメントを除去
            normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
            # 末尾のスラッシュを統一
            if normalized.endswith('/'):
                normalized = normalized[:-1]
            return normalized.lower()  # 大文字小文字を統一
        except:
            return url
    
    def _is_duplicate_content(self, title: str, existing_titles: List[str]) -> bool:
        """タイトルの類似度をチェックして重複コンテンツかどうか判定（強化版）"""
        import re
        
        def normalize_title(t):
            # タイトルを正規化（小文字化、記号除去、単語分割）
            t = t.lower()
            # 中国語・日本語の句読点も除去
            t = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', ' ', t)
            # 連続する空白を1つに
            t = re.sub(r'\s+', ' ', t).strip()
            return set(t.split())
        
        def get_key_phrases(t):
            """タイトルから重要なフレーズを抽出"""
            t_lower = t.lower()
            # 特定の重要キーワードを抽出
            keywords = []
            # 航空会社・飛行機関連
            if 'airbus' in t_lower or 'エアバス' in t_lower:
                keywords.append('airbus')
            if 'a320' in t_lower or 'a320' in t_lower:
                keywords.append('a320')
            # 性犯罪関連
            if 'sexual crime' in t_lower or '性犯罪' in t_lower:
                keywords.append('sexual_crime')
            if 'consent' in t_lower or '同意' in t_lower:
                keywords.append('consent')
            # 火災関連
            if 'wang fuk' in t_lower or '宏福苑' in t_lower:
                keywords.append('wang_fuk')
            if 'fire' in t_lower or '火災' in t_lower or '大火' in t_lower:
                keywords.append('fire')
            return keywords
        
        title_words = normalize_title(title)
        title_phrases = get_key_phrases(title)
        
        if not title_words:
            return False
        
        for existing in existing_titles:
            existing_words = normalize_title(existing)
            existing_phrases = get_key_phrases(existing)
            
            if not existing_words:
                continue
            
            # キーフレーズが2つ以上一致したら重複とみなす
            if len(title_phrases) >= 2 and len(existing_phrases) >= 2:
                common_phrases = set(title_phrases) & set(existing_phrases)
                if len(common_phrases) >= 2:
                    return True
            
            common_words = title_words & existing_words
            shortest_len = min(len(title_words), len(existing_words))
            
            # 最小共通語数の条件を厳しく
            if shortest_len <= 3:
                min_common = shortest_len  # 短いタイトルは全単語一致が必要
            elif shortest_len <= 6:
                min_common = max(3, int(shortest_len * 0.7))  # 70%以上一致
            else:
                min_common = max(4, int(shortest_len * 0.6))  # 60%以上一致
            
            if len(common_words) < min_common:
                continue
            
            all_words = title_words | existing_words
            similarity = len(common_words) / len(all_words) if all_words else 0.0
            coverage = len(common_words) / shortest_len if shortest_len else 0.0
            
            # 類似度の閾値を厳しく（0.5 → 0.4、0.6 → 0.5に変更）
            if similarity >= 0.4 and coverage >= 0.5:
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
            
            for entry in feed.entries[:50]:
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
            
            for entry in feed.entries[:50]:
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
            
            for entry in feed.entries[:50]:
                url = entry.get('link', '')
                if self._has_been_processed(url):
                    filtered_count += 1
                    continue
                if self._is_url_too_old(url):
                    filtered_count += 1
                    self._mark_url_as_processed(url)
                    continue
                published_at = entry.get('published', entry.get('updated', ''))
                title = self._clean_feed_text(entry.get('title', ''))
                description = self._clean_feed_text(entry.get('summary', entry.get('description', '')))
                
                # 日付フィルタリング
                if not self._is_today_news(published_at):
                    filtered_count += 1
                    continue
                
                # 禁止コンテンツフィルタリング
                if self._is_forbidden_content(title, description):
                    filtered_count += 1
                    continue

                # Google News HKからの記事はより厳格な香港関連チェックを適用
                if not self._is_hk_related(title, description, url, 'Google News HK'):
                    filtered_count += 1
                    continue
                
                # 24時間以内の記事のみ（追加チェック）
                if published_at:
                    try:
                        pub_date = date_parser.parse(published_at)
                        now = datetime.now(HKT)
                        time_diff = now - pub_date.replace(tzinfo=None)
                        if time_diff.total_seconds() > 24 * 3600:
                            filtered_count += 1
                            continue
                    except:
                        pass  # パース失敗は含める
                
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
            
            for entry in feed.entries[:50]:
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
            
            for entry in feed.entries[:50]:
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
                
                for entry in feed.entries[:50]:
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
            
            for entry in feed.entries[:50]:
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
        
        # Phase 1: スクレイピング（HK01、明報、am730などRSSが存在しないサイト）
        # ※ Playwright は CI で極端に遅いため GITHUB_ACTIONS 時はスキップ（RSS のみで十分な補完）
        print("\n📰 Phase 1: Webスクレイピング")
        print("-" * 60)
        scraped_news = []
        scraped_added = 0

        if not _should_run_playwright_news_scrape():
            print(
                "⏭️  Phase 1 をスキップ（高速モード）: "
                "GitHub Actions では Playwright 一覧取得を行わず RSS のみ。"
                " 一覧スクレイピングも使う場合は RUN_PLAYWRIGHT_NEWS_SCRAPE=1"
            )
        else:
            try:
                from scrape_news_list import NewsListScraper
                scraper = NewsListScraper()
                scraped_news = scraper.fetch_all_news()

                # スクレイピング結果を追加
                for news in scraped_news:
                    url = news.get('url', '')
                    title = news.get('title', '')
                    normalized_url = self._normalize_url(url)

                    # 重複チェック
                    if normalized_url and normalized_url in existing_urls:
                        continue
                    if self._is_duplicate_content(title, existing_titles):
                        continue

                    # 日付フィルタリング
                    published_at = news.get('published_at', '')
                    if published_at and not self._is_today_news(published_at):
                        continue

                    # 禁止コンテンツフィルタリング
                    if self._is_forbidden_content(title, news.get('description', '')):
                        continue

                    # 香港関連度チェック
                    if not self._is_hk_related(title, news.get('description', ''), url, news.get('source', '')):
                        continue

                    all_news.append({
                        'title': title,
                        'description': news.get('description', title),
                        'url': url,
                        'published_at': published_at or datetime.now(HKT).isoformat(),
                        'source': news.get('source', 'Scraped'),
                        'api_source': 'web_scraping'
                    })
                    existing_urls.add(normalized_url)
                    existing_titles.append(title)
                    scraped_added += 1

                print(f"✅ スクレイピング: {len(scraped_news)}件取得 → {scraped_added}件追加")
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
            (self.fetch_google_news_rss, None, None),  # 香港トピック（24時間以内フィルタリング適用）
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
