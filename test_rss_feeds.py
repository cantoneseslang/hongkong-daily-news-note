#!/usr/bin/env python3
import requests
from datetime import datetime

feeds_to_test = {
    # 現在使用中
    'SCMP Hong Kong': 'https://www.scmp.com/rss/2/feed',
    'SCMP Business': 'https://www.scmp.com/rss/5/feed',
    'SCMP Lifestyle': 'https://www.scmp.com/rss/322184/feed',
    'RTHK News': 'https://rthk.hk/rthk/news/rss/e_expressnews_elocal.xml',
    'RTHK Business': 'https://rthk.hk/rthk/news/rss/e_expressnews_ebusiness.xml',
    'Yahoo HK': 'http://hk.news.yahoo.com/rss/hong-kong',
    'Google News HK': 'http://news.google.com.hk/news?pz=1&cf=all&ned=hk&hl=zh-TW&output=rss',
    'China Daily HK': 'http://www.chinadaily.com.cn/rss/hk_rss.xml',
    'HKFP': 'https://www.hongkongfp.com/feed/',
    'HKet HK': 'https://www.hket.com/rss/hongkong',
    'HKet Finance': 'https://www.hket.com/rss/finance',
    'HKet Property': 'https://www.hket.com/rss/property',
    
    # 新規候補
    'The Standard': 'https://www.thestandard.com.hk/rss/latest',
    'HK01 即時': 'https://www.hk01.com/rss/01feed',
    'Gov HK': 'https://www.news.gov.hk/rss/en/govhknews.xml',
    'RTHK中文': 'https://rthk.hk/rthk/news/rss/c_expressnews_clocal.xml',
}

print(f"{'RSS Feed':<30} {'Status':<10} {'Items':<10}")
print("=" * 60)

for name, url in feeds_to_test.items():
    try:
        resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            # 簡易的にitemタグの数を数える
            item_count = resp.text.count('<item>')
            if item_count == 0:
                item_count = resp.text.count('<entry>')
            status = "✅ OK"
            items = f"{item_count} items"
        else:
            status = f"❌ {resp.status_code}"
            items = "-"
    except Exception as e:
        status = "❌ Error"
        items = str(e)[:20]
    
    print(f"{name:<30} {status:<10} {items:<10}")

print("\n実行完了:", datetime.now())
