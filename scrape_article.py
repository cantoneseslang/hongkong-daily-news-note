#!/usr/bin/env python3
"""
ニュース記事の全文をスクレイピング
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import time

class ArticleScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def scrape_article(self, url: str) -> Optional[str]:
        """URLから記事全文を取得"""
        try:
            # Hong Kong Free Pressを除外
            if 'hongkongfp.com' in url.lower():
                print(f"  ⏭️  スキップ: Hong Kong Free Press")
                return None
            
            # 広告記事を除外
            if '/presented/' in url.lower() or '/sponsored/' in url.lower() or '/advertorial/' in url.lower():
                print(f"  ⏭️  スキップ: 広告記事")
                return None
            
            print(f"  📰 記事取得中: {url[:60]}...")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # サイト別のセレクター
            if 'thestandard.com.hk' in url:
                content = self._scrape_standard(soup)
            elif 'scmp.com' in url:
                content = self._scrape_scmp(soup)
            else:
                # 一般的な記事構造を試す
                content = self._scrape_generic(soup)
            
            if content and len(content) > 200:
                print(f"    ✅ {len(content)}文字取得")
                return content
            else:
                print(f"    ⚠️  記事本文が短すぎる")
                return None
                
        except Exception as e:
            print(f"    ❌ スクレイピング失敗: {e}")
            return None
    
    def _scrape_standard(self, soup: BeautifulSoup) -> Optional[str]:
        """The Standard専用"""
        # 複数のセレクターを試す
        selectors = [
            ('div', {'class': 'article-content'}),
            ('div', {'class': 'article-body'}),
            ('div', {'class': 'content'}),
            ('article', {}),
            ('div', {'id': 'article-content'}),
        ]
        
        for tag, attrs in selectors:
            article = soup.find(tag, attrs)
            if article:
                paragraphs = article.find_all('p')
                if paragraphs:
                    content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                    if len(content) > 100:
                        return content
        
        # フォールバック：全てのpタグを取得
        paragraphs = soup.find_all('p')
        if paragraphs:
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip() and len(p.get_text()) > 50])
            return content
        
        return None
    
    def _scrape_scmp(self, soup: BeautifulSoup) -> Optional[str]:
        """South China Morning Post専用"""
        article = soup.find('article')
        if article:
            paragraphs = article.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            return content
        return None
    
    def _scrape_generic(self, soup: BeautifulSoup) -> Optional[str]:
        """一般的な記事構造"""
        # articleタグを探す
        article = soup.find('article')
        if not article:
            # main contentを探す
            article = soup.find('div', class_=['content', 'article-content', 'post-content', 'entry-content'])
        
        if article:
            paragraphs = article.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            return content
        return None
    
    def enrich_news_data(self, news_list: list) -> list:
        """ニュースデータに全文を追加"""
        print("\n📰 記事全文を取得中...")
        print("=" * 60)
        
        enriched = []
        for i, news in enumerate(news_list, 1):
            print(f"\n[{i}/{len(news_list)}]")
            
            full_content = self.scrape_article(news['url'])
            
            news_enriched = news.copy()
            if full_content:
                news_enriched['full_content'] = full_content
            else:
                # フォールバック: descriptionを使用
                news_enriched['full_content'] = news.get('description', '')
            
            enriched.append(news_enriched)
            
            # レート制限対策
            time.sleep(1)
        
        print("\n" + "=" * 60)
        print(f"✅ 全文取得完了: {len(enriched)}件\n")
        
        return enriched

if __name__ == "__main__":
    import json
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python scrape_article.py <raw_news.json>")
        sys.exit(1)
    
    news_file = sys.argv[1]
    
    with open(news_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    scraper = ArticleScraper()
    enriched_news = scraper.enrich_news_data(data['news'])
    
    # 保存
    output_file = news_file.replace('.json', '_enriched.json')
    data['news'] = enriched_news
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 保存完了: {output_file}")

