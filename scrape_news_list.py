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
            # HK01の主要セクション（トップページとカテゴリページ）
            urls = [
                'https://www.hk01.com/',  # トップページ
                'https://www.hk01.com/zone/1',  # 港聞
                'https://www.hk01.com/channel/310',  # 政情
                'https://www.hk01.com/channel/4',  # 經濟
            ]
            
            if self.use_playwright:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        viewport={'width': 1920, 'height': 1080}
                    )
                    page = context.new_page()
                    
                    for url in urls:
                        try:
                            print(f"  📄 {url} を読み込み中...")
                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            page.wait_for_timeout(8000)  # JavaScriptの実行を待つ（8秒に増加）
                            
                            # HK01はNext.jsのSPAで、記事データはJSONに埋め込まれている
                            # ページ内のJSONデータから記事情報を抽出
                            try:
                                # __NEXT_DATA__スクリプトタグからJSONを取得
                                json_script = page.query_selector('script#__NEXT_DATA__')
                                if json_script:
                                    json_text = json_script.inner_text()
                                    import json as json_lib
                                    data = json_lib.loads(json_text)
                                    
                                    # 記事データを抽出
                                    articles_data = []
                                    
                                    # props.initialProps.pageProps.sections から記事を取得
                                    def extract_articles_from_data(data_obj, articles_list):
                                        """再帰的に記事データを抽出"""
                                        if isinstance(data_obj, dict):
                                            # 記事データのパターン1: data.articleId と data.canonicalUrl がある
                                            if 'articleId' in data_obj and 'canonicalUrl' in data_obj:
                                                article_url = data_obj.get('canonicalUrl', '')
                                                article_title = data_obj.get('title', '')
                                                article_id = data_obj.get('articleId', '')
                                                
                                                if article_url and ('/article/' in article_url or article_id):
                                                    # URL正規化
                                                    if article_url.startswith('/'):
                                                        full_url = urljoin('https://www.hk01.com', article_url)
                                                    elif article_url.startswith('http'):
                                                        full_url = article_url.split('?')[0].split('#')[0]
                                                    else:
                                                        # articleIdからURLを構築
                                                        full_url = f"https://www.hk01.com/article/{article_id}"
                                                    
                                                    if article_title and len(article_title) > 5:
                                                        articles_list.append({
                                                            'title': article_title,
                                                            'url': full_url,
                                                            'id': article_id
                                                        })
                                            else:
                                                # 再帰的に探索
                                                for key, value in data_obj.items():
                                                    extract_articles_from_data(value, articles_list)
                                        elif isinstance(data_obj, list):
                                            for item in data_obj:
                                                extract_articles_from_data(item, articles_list)
                                    
                                    # データ構造を探索
                                    if 'props' in data:
                                        extract_articles_from_data(data['props'], articles_data)
                                    
                                    print(f"    📰 JSONから {len(articles_data)}件の記事を抽出")
                                    
                                    # 記事データをnews_listに追加
                                    for article_data in articles_data[:100]:  # 最大100件
                                        # 重複チェック
                                        if not any(n['url'] == article_data['url'] for n in news_list):
                                            news_list.append({
                                                'title': article_data['title'],
                                                'url': article_data['url'],
                                                'source': 'HK01',
                                                'published_at': datetime.now(HKT).isoformat()
                                            })
                                    
                                    if len(articles_data) > 0:
                                        continue  # JSONから取得できたので、次のURLへ
                            except Exception as e:
                                print(f"    ⚠️  JSON抽出エラー: {e}")
                            
                            # フォールバック: HTMLからリンクを取得
                            print("    🔍 HTMLからリンクを取得中...")
                            selectors = [
                                'a[href*="/article/"]',
                                'a[href^="/article/"]',
                            ]
                            
                            articles = []
                            for selector in selectors:
                                found = page.query_selector_all(selector)
                                if found:
                                    articles.extend(found)
                                    if len(articles) >= 50:
                                        break
                            
                            print(f"    📰 HTMLリンク: {len(articles)}件")
                            
                            for article in articles[:100]:  # 最大100件まで
                                try:
                                    href = article.get_attribute('href')
                                    if not href:
                                        continue
                                    
                                    # articleを含むURLのみを対象（広告やJSファイルを除外）
                                    if '/article/' not in href and 'article' not in href.lower():
                                        continue
                                    
                                    # JavaScriptファイルや広告URLを除外
                                    if '/_next/' in href or 'omgt3.com' in href or 'clk.' in href or '.js' in href:
                                        continue
                                    
                                    # URL正規化
                                    if href.startswith('/'):
                                        full_url = urljoin('https://www.hk01.com', href)
                                    elif href.startswith('http'):
                                        full_url = href
                                    else:
                                        continue
                                    
                                    # クエリパラメータを除去して正規化
                                    full_url = full_url.split('?')[0].split('#')[0]
                                    
                                    # 重複チェック（URLベース）- 先にチェック
                                    if any(n['url'] == full_url for n in news_list):
                                        continue
                                    
                                    # タイトル取得（複数の方法を試す）
                                    title = None
                                    title_selectors = ['h2', 'h3', 'h4', '.title', '.article-title', '[class*="title"]', 'span', 'div']
                                    
                                    for title_sel in title_selectors:
                                        try:
                                            title_elem = article.query_selector(title_sel)
                                            if title_elem:
                                                title_text = title_elem.inner_text().strip()
                                                if title_text and len(title_text) > 5:
                                                    title = title_text
                                                    break
                                        except:
                                            continue
                                    
                                    # セレクタで見つからない場合は、リンクのテキストを使用
                                    if not title or len(title) <= 5:
                                        try:
                                            title = article.inner_text().strip()
                                        except:
                                            title = ''
                                    
                                    # タイトルが有効な場合のみ追加
                                    if title and len(title) > 5 and len(title) < 300:
                                        # 広告や不要なテキストを除外
                                        if any(skip in title.lower() for skip in ['廣告', 'advertisement', '推廣', 'promotion', 'click here', 'javascript']):
                                            continue
                                        
                                        news_list.append({
                                            'title': title,
                                            'url': full_url,
                                            'source': 'HK01',
                                            'published_at': datetime.now(HKT).isoformat()
                                        })
                                        
                                        # デバッグ: 最初の5件を表示
                                        if len([n for n in news_list if n.get('source') == 'HK01']) <= 5:
                                            print(f"      ✅ 取得: {title[:50]}... | {full_url}")
                                except Exception as e:
                                    # デバッグ: 最初のエラーのみ表示
                                    if len(news_list) == 0:
                                        print(f"      ⚠️  エラー: {e}")
                                    continue
                            
                            time.sleep(2)  # リクエスト間隔を2秒に
                        except Exception as e:
                            print(f"  ⚠️  {url} でエラー: {e}")
                            import traceback
                            traceback.print_exc()
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
