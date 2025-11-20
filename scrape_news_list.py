#!/usr/bin/env python3
"""
香港ニュースサイトから直接ニュース一覧をスクレイピング（Playwright使用）
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import time
import re
from urllib.parse import urljoin

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

# Playwrightのインポート（フォールバック付き）
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️  Playwright not available, falling back to requests")

class NewsListScraper:
    def __init__(self):
        self.use_playwright = PLAYWRIGHT_AVAILABLE
        self.requests = None
        self.BeautifulSoup = None
        self.session = None
        
        if not self.use_playwright:
            # フォールバック: requests + BeautifulSoup
            try:
                import requests
                from bs4 import BeautifulSoup
                self.requests = requests
                self.BeautifulSoup = BeautifulSoup
                self.headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9,zh-HK;q=0.8,zh;q=0.7',
                }
                self.session = requests.Session()
                self.session.headers.update(self.headers)
            except ImportError:
                print("⚠️  requests/BeautifulSoup also not available")
                self.session = None
    
    def scrape_hk01(self) -> List[Dict]:
        """HK01（香港01）から取得 - RSSが存在しないためスクレイピング"""
        print("\n📰 HK01 からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.hk01.com/zone/1/港聞',  # 港聞
                'https://www.hk01.com/channel/2/社會新聞',  # 社會新聞
                'https://www.hk01.com/channel/310/政情',  # 政情
                'https://www.hk01.com/channel/4/經濟',  # 經濟
            ]
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    for url in urls:
                        try:
                            print(f"  📄 {url} を読み込み中...")
                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            page.wait_for_timeout(5000)  # JavaScriptの実行を待つ
                            
                            # HK01の記事リンクを取得
                            articles = page.query_selector_all('a[href*="/article/"]')
                            
                            for article in articles[:30]:
                                try:
                                    href = article.get_attribute('href')
                                    if not href:
                                        continue
                                    
                                    full_url = urljoin('https://www.hk01.com', href)
                                    
                                    # タイトル取得
                                    title_elem = article.query_selector('h2, h3, h4, .article-title')
                                    if not title_elem:
                                        title = article.inner_text().strip()
                                    else:
                                        title = title_elem.inner_text().strip()
                                    
                                    if title and len(title) > 5:
                                        news_list.append({
                                            'title': title,
                                            'url': full_url,
                                            'source': 'HK01',
                                            'published_at': datetime.now(HKT).isoformat()
                                        })
                                except Exception:
                                    continue
                            
                            time.sleep(1)
                        except Exception as e:
                            print(f"  ⚠️  {url} でエラー: {e}")
                            continue
                    
                    browser.close()
            else:
                # フォールバック（requestsでは取得困難）
                print("  ⚠️  HK01はJavaScriptで動的生成されるため、Playwrightが必要です")
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def scrape_mingpao(self) -> List[Dict]:
        """明報（Ming Pao）から取得 - RSSが存在しないためスクレイピング"""
        print("\n📰 明報 からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://news.mingpao.com/pns/港聞',
                'https://news.mingpao.com/pns/要聞',
            ]
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    for url in urls:
                        try:
                            print(f"  📄 {url} を読み込み中...")
                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            page.wait_for_timeout(5000)
                            
                            articles = page.query_selector_all('a[href*="/pns/"]')
                            
                            for article in articles[:30]:
                                try:
                                    href = article.get_attribute('href')
                                    if not href or '/article/' not in href:
                                        continue
                                    
                                    full_url = urljoin('https://news.mingpao.com', href)
                                    title = article.inner_text().strip()
                                    
                                    if title and len(title) > 5:
                                        news_list.append({
                                            'title': title,
                                            'url': full_url,
                                            'source': '明報',
                                            'published_at': datetime.now(HKT).isoformat()
                                        })
                                except Exception:
                                    continue
                            
                            time.sleep(1)
                        except Exception as e:
                            print(f"  ⚠️  {url} でエラー: {e}")
                            continue
                    
                    browser.close()
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def scrape_am730(self) -> List[Dict]:
        """am730から取得 - RSSが存在しないためスクレイピング"""
        print("\n📰 am730 からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.am730.com.hk/news',
                'https://www.am730.com.hk/news/local',
            ]
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    for url in urls:
                        try:
                            print(f"  📄 {url} を読み込み中...")
                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            page.wait_for_timeout(5000)
                            
                            articles = page.query_selector_all('a[href*="/news/"]')
                            
                            for article in articles[:30]:
                                try:
                                    href = article.get_attribute('href')
                                    if not href or '/news/' not in href:
                                        continue
                                    
                                    full_url = urljoin('https://www.am730.com.hk', href)
                                    title = article.inner_text().strip()
                                    
                                    if title and len(title) > 5:
                                        news_list.append({
                                            'title': title,
                                            'url': full_url,
                                            'source': 'am730',
                                            'published_at': datetime.now(HKT).isoformat()
                                        })
                                except Exception:
                                    continue
                            
                            time.sleep(1)
                        except Exception as e:
                            print(f"  ⚠️  {url} でエラー: {e}")
                            continue
                    
                    browser.close()
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return []
    
    def scrape_scmp_hongkong(self) -> List[Dict]:
        """SCMP 香港ニュースセクションから取得"""
        print("\n📰 SCMP Hong Kong からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.scmp.com/news/hong-kong',
                'https://www.scmp.com/news/hong-kong/politics',
                'https://www.scmp.com/news/hong-kong/society',
            ]
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    for url in urls:
                        try:
                            print(f"  📄 {url} を読み込み中...")
                            page.goto(url, wait_until='networkidle', timeout=30000)
                            page.wait_for_timeout(2000)  # JavaScriptの実行を待つ
                            
                            # 記事リンクを取得
                            articles = page.query_selector_all('a[href*="/article/"]')
                            
                            for article in articles[:30]:
                                try:
                                    href = article.get_attribute('href')
                                    if not href:
                                        continue
                                    
                                    full_url = urljoin('https://www.scmp.com', href)
                                    
                                    # タイトル取得
                                    title_elem = article.query_selector('h2, h3, h4, span')
                                    if not title_elem:
                                        title = article.inner_text().strip()
                                    else:
                                        title = title_elem.inner_text().strip()
                                    
                                    if title and len(title) > 10:
                                        news_list.append({
                                            'title': title,
                                            'url': full_url,
                                            'source': 'SCMP',
                                            'published_at': datetime.now(HKT).isoformat()
                                        })
                                except Exception as e:
                                    continue
                            
                            time.sleep(1)
                        except Exception as e:
                            print(f"  ⚠️  {url} でエラー: {e}")
                            continue
                    
                    browser.close()
            elif self.session:
                # フォールバック: requests
                for url in urls:
                    try:
                        response = self.session.get(url, timeout=10)
                        response.raise_for_status()
                        soup = self.BeautifulSoup(response.content, 'html.parser')
                        
                        articles = soup.find_all('a', href=re.compile(r'/article/\d+'))
                        
                        for article in articles[:20]:
                            href = article.get('href')
                            if not href:
                                continue
                            
                            full_url = urljoin('https://www.scmp.com', href)
                            title_elem = article.find(['h2', 'h3', 'h4', 'span'])
                            if not title_elem:
                                title_elem = article
                            title = title_elem.get_text(strip=True)
                            
                            if title and len(title) > 10:
                                news_list.append({
                                    'title': title,
                                    'url': full_url,
                                    'source': 'SCMP',
                                    'published_at': datetime.now(HKT).isoformat()
                                })
                        
                        time.sleep(1)
                    except Exception as e:
                        print(f"  ⚠️  {url} でエラー: {e}")
                        continue
            
            # 重複除去
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def scrape_thestandard(self) -> List[Dict]:
        """The Standard から取得"""
        print("\n📰 The Standard からスクレイピング中...")
        news_list = []
        
        try:
            urls = [
                'https://www.thestandard.com.hk/section/2/latest',
                'https://www.thestandard.com.hk/section/4/latest',
            ]
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    for url in urls:
                        try:
                            print(f"  📄 {url} を読み込み中...")
                            page.goto(url, wait_until='networkidle', timeout=30000)
                            page.wait_for_timeout(2000)
                            
                            articles = page.query_selector_all('a[href*="/article/"]')
                            
                            for article in articles[:30]:
                                try:
                                    href = article.get_attribute('href')
                                    if not href:
                                        continue
                                    
                                    full_url = urljoin('https://www.thestandard.com.hk', href)
                                    title = article.inner_text().strip()
                                    
                                    if title and len(title) > 10:
                                        news_list.append({
                                            'title': title,
                                            'url': full_url,
                                            'source': 'The Standard',
                                            'published_at': datetime.now(HKT).isoformat()
                                        })
                                except Exception:
                                    continue
                            
                            time.sleep(1)
                        except Exception as e:
                            print(f"  ⚠️  {url} でエラー: {e}")
                            continue
                    
                    browser.close()
            elif self.session:
                # フォールバック
                for url in urls:
                    try:
                        response = self.session.get(url, timeout=10)
                        response.raise_for_status()
                        soup = self.BeautifulSoup(response.content, 'html.parser')
                        
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
                                    'source': 'The Standard',
                                    'published_at': datetime.now(HKT).isoformat()
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
            import traceback
            traceback.print_exc()
            return []
    
    def scrape_rthk_news(self) -> List[Dict]:
        """RTHK English News から取得"""
        print("\n📰 RTHK News からスクレイピング中...")
        news_list = []
        
        try:
            url = 'https://news.rthk.hk/rthk/en/component/k2/index-archive.htm'
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    try:
                        print(f"  📄 {url} を読み込み中...")
                        page.goto(url, wait_until='networkidle', timeout=30000)
                        page.wait_for_timeout(2000)
                        
                        articles = page.query_selector_all('a[href*="/component/k2/"]')
                        
                        for article in articles[:50]:
                            try:
                                href = article.get_attribute('href')
                                if not href:
                                    continue
                                
                                full_url = urljoin('https://news.rthk.hk', href)
                                title = article.inner_text().strip()
                                
                                if title and len(title) > 10:
                                    news_list.append({
                                        'title': title,
                                        'url': full_url,
                                        'source': 'RTHK',
                                        'published_at': datetime.now(HKT).isoformat()
                                    })
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"  ⚠️  {url} でエラー: {e}")
                    
                    browser.close()
            elif self.session:
                # フォールバック
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    soup = self.BeautifulSoup(response.content, 'html.parser')
                    
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
                                'source': 'RTHK',
                                'published_at': datetime.now(HKT).isoformat()
                            })
                except Exception as e:
                    print(f"  ⚠️  {url} でエラー: {e}")
            
            unique_news = self._deduplicate_by_url(news_list)
            print(f"  ✅ {len(unique_news)}件取得")
            return unique_news
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _deduplicate_by_url(self, news_list: List[Dict]) -> List[Dict]:
        """URL重複を除去"""
        seen_urls = set()
        unique_news = []
        
        for news in news_list:
            url = news.get('url', '')
            normalized_url = url.split('?')[0]
            
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_news.append(news)
        
        return unique_news
    
    def fetch_all_news(self) -> List[Dict]:
        """全サイトからニュースを取得"""
        print("\n" + "=" * 60)
        print("🚀 ニュース一覧スクレイピング開始")
        if self.use_playwright:
            print("📦 Playwright使用")
        else:
            print("📦 Requests使用（フォールバック）")
        print("=" * 60)
        
        all_news = []
        
        # 各サイトから取得（RSSが存在しない、または取得できないサイトのみ）
        scrapers = [
            self.scrape_hk01,  # HK01 - RSSが存在しない
            self.scrape_mingpao,  # 明報 - RSSが存在しない
            self.scrape_am730,  # am730 - RSSが存在しない
            # SCMP, The Standard, RTHKはRSSで取得済みのため除外
        ]
        
        for scraper in scrapers:
            try:
                news = scraper()
                all_news.extend(news)
            except Exception as e:
                print(f"  ❌ スクレイパーエラー: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 全体で重複除去
        unique_news = self._deduplicate_by_url(all_news)
        
        print("\n" + "=" * 60)
        print(f"✅ 合計 {len(unique_news)}件のニュースを取得")
        print("=" * 60)
        
        # 現在時刻とソース統計を追加
        result = []
        for news in unique_news:
            news['description'] = news.get('title', '')  # 後で全文取得で上書き
            news['api_source'] = 'web_scraping'
            result.append(news)
        
        return result

if __name__ == "__main__":
    import json
    
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
        from collections import Counter
        sources = Counter([n.get('source', 'Unknown') for n in news_list])
        
        print("\n📊 ソース別統計:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}件")
    else:
        print("\n❌ ニュースが取得できませんでした")
