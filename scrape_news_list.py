#!/usr/bin/env python3
"""
香港ニュースサイトから直接ニュース一覧をスクレイピング
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import time
import re
from urllib.parse import urljoin, urlparse

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class NewsListScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-HK;q=0.8,zh;q=0.7',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def scrape_scmp_hongkong(self) -> List[Dict]:
        """SCMP 香港ニュースセクションから取得"""
        print("\n📰 SCMP Hong Kong からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.scmp.com/news/hong-kong',
                'https://www.scmp.com/news/hong-kong/politics',
                'https://www.scmp.com/news/hong-kong/society',
                'https://www.scmp.com/news/hong-kong/health-environment',
                'https://www.scmp.com/business/companies',
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # SCMPの記事リンクを探す
                    articles = soup.find_all('a', href=re.compile(r'/article/\d+'))
                    
                    for article in articles[:20]:  # 各ページから20件
                        href = article.get('href')
                        if not href:
                            continue
                        
                        full_url = urljoin('https://www.scmp.com', href)
                        
                        # タイトル取得
                        title_elem = article.find(['h2', 'h3', 'h4', 'span'])
                        if not title_elem:
                            title_elem = article
                        title = title_elem.get_text(strip=True)
                        
                        if title and len(title) > 10:
                            news_list.append({
                                'title': title,
                                'url': full_url,
                                'source': 'SCMP',
                                'category': url.split('/')[-1]
                            })
                    
                    time.sleep(1)  # レート制限対策
                except Exception as e:
                    print(f"  ⚠️  {url} でエラー: {e}")
                    continue
            
            # 重複除去
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def scrape_thestandard(self) -> List[Dict]:
        """The Standard から取得"""
        print("\n📰 The Standard からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.thestandard.com.hk/section/2/latest',
                'https://www.thestandard.com.hk/section/4/latest',
                'https://www.thestandard.com.hk/section/11/latest',
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 記事リンクを探す
                    articles = soup.find_all('a', href=re.compile(r'/[a-z-]+/article/\d+'))
                    
                    for article in articles[:30]:
                        href = article.get('href')
                        if not href:
                            continue
                        
                        full_url = urljoin('https://www.thestandard.com.hk', href)
                        
                        title_elem = article.find(['h2', 'h3', 'h4'])
                        if not title_elem:
                            title_elem = article
                        title = title_elem.get_text(strip=True)
                        
                        if title and len(title) > 10:
                            news_list.append({
                                'title': title,
                                'url': full_url,
                                'source': 'The Standard'
                            })
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️  {url} でエラー: {e}")
                    continue
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def scrape_rthk_news(self) -> List[Dict]:
        """RTHK English News から取得"""
        print("\n📰 RTHK News からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://news.rthk.hk/rthk/en/component/k2/index-archive.htm',
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # RTHKの記事構造を探す
                    articles = soup.find_all('a', href=re.compile(r'/rthk/en/component/k2/\d+'))
                    
                    for article in articles[:40]:
                        href = article.get('href')
                        if not href:
                            continue
                        
                        full_url = urljoin('https://news.rthk.hk', href)
                        title = article.get_text(strip=True)
                        
                        if title and len(title) > 10:
                            news_list.append({
                                'title': title,
                                'url': full_url,
                                'source': 'RTHK'
                            })
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️  {url} でエラー: {e}")
                    continue
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def scrape_hk01(self) -> List[Dict]:
        """HK01 から取得（中国語サイト）"""
        print("\n📰 HK01 からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.hk01.com/zone/1/港聞',
                'https://www.hk01.com/channel/2/社會新聞',
                'https://www.hk01.com/channel/310/政情',
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # HK01の記事リンクを探す
                    articles = soup.find_all('a', href=re.compile(r'/article/\d+'))
                    
                    for article in articles[:30]:
                        href = article.get('href')
                        if not href:
                            continue
                        
                        full_url = urljoin('https://www.hk01.com', href)
                        
                        # タイトル取得
                        title_elem = article.find(['h2', 'h3', 'h4'])
                        if not title_elem:
                            title_elem = article
                        title = title_elem.get_text(strip=True)
                        
                        if title and len(title) > 5:
                            news_list.append({
                                'title': title,
                                'url': full_url,
                                'source': 'HK01'
                            })
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️  {url} でエラー: {e}")
                    continue
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def scrape_chinadaily_hk(self) -> List[Dict]:
        """China Daily HK Edition から取得"""
        print("\n📰 China Daily HK からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.chinadailyhk.com/hk',
                'https://www.chinadailyhk.com/hong-kong',
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 記事リンクを探す
                    articles = soup.find_all('a', href=re.compile(r'/article/\d+|/articles/\d+'))
                    
                    for article in articles[:30]:
                        href = article.get('href')
                        if not href:
                            continue
                        
                        full_url = urljoin('https://www.chinadailyhk.com', href)
                        
                        title_elem = article.find(['h2', 'h3', 'h4'])
                        if not title_elem:
                            title_elem = article
                        title = title_elem.get_text(strip=True)
                        
                        if title and len(title) > 10:
                            news_list.append({
                                'title': title,
                                'url': full_url,
                                'source': 'China Daily HK'
                            })
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️  {url} でエラー: {e}")
                    continue
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def _deduplicate_by_url(self, news_list: List[Dict]) -> List[Dict]:
        """URL重複を除去"""
        seen_urls = set()
        unique_news = []
        
        for news in news_list:
            url = news.get('url', '')
            # URLを正規化（クエリパラメータ除去）
            normalized_url = url.split('?')[0]
            
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_news.append(news)
        
        return unique_news
    
    def fetch_all_news(self) -> List[Dict]:
        """全サイトからニュースを取得"""
        print("\n" + "=" * 60)
        print("🚀 ニュース一覧スクレイピング開始")
        print("=" * 60)
        
        all_news = []
        
        # 各サイトから取得
        scrapers = [
            self.scrape_scmp_hongkong,
            self.scrape_thestandard,
            self.scrape_rthk_news,
            self.scrape_hk01,
            self.scrape_chinadaily_hk,
        ]
        
        for scraper in scrapers:
            try:
                news = scraper()
                all_news.extend(news)
            except Exception as e:
                print(f"  ❌ スクレイパーエラー: {e}")
                continue
        
        # 全体で重複除去
        unique_news = self._deduplicate_by_url(all_news)
        
        print("\n" + "=" * 60)
        print(f"✅ 合計 {len(unique_news)}件のニュースを取得")
        print("=" * 60)
        
        # 現在時刻とソース統計を追加
        result = []
        for news in unique_news:
            news['published_at'] = datetime.now(HKT).isoformat()
            news['description'] = news.get('title', '')  # 後で全文取得で上書き
            news['api_source'] = 'web_scraping'
            result.append(news)
        
        return result

if __name__ == "__main__":
    import json
    import sys
    
    scraper = NewsListScraper()
    news_list = scraper.fetch_all_news()
    
    if news_list:
        # JSONで保存
        output_file = f'daily-articles/scraped_news_{datetime.now(HKT).strftime("%Y-%m-%d_%H-%M-%S")}.json'
        
        output_data = {
            'fetch_time': datetime.now(HKT).isoformat(),
            'total_count': len(news_list),
            'news': news_list
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 保存完了: {output_file}")
        
        # ソース別統計
        sources = {}
        for news in news_list:
            source = news.get('source', 'Unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print("\n📊 ソース別統計:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}件")
    else:
        print("\n❌ ニュースが取得できませんでした")
        sys.exit(1)

