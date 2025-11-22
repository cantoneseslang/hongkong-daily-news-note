# ニュース取得の根本問題と解決策

## 🔴 現状の問題

### 取得数が極端に少ない
- **11月19日**: わずか13件（重複込み）
- **正常な場合**: 50〜100件以上

### 取得内容の質が低い
```
13件の内訳:
❌ トランプ/テキサス選挙 × 2（香港無関係）
❌ CATL株 × 2（中国企業）
❌ Meta独占禁止法（米国）
❌ 中国清朝の歴史
❌ 中国の高齢化社会
❌ National Games（全国運動会）× 2
❌ Ace Green Recycling（香港無関係）
✅ HKサッカー × 2
✅ Xpeng（若干香港関連）
```

---

## 🔍 原因分析

### 1. RSSフィードの取得が機能していない可能性
- GitHub Actionsで`rss_news_*.json`が生成されているはず
- しかし実際は13件しかない
- RSSパーサーのエラーか、フィード自体の問題か

### 2. 現在のRSSソースが少ない
```python
rss_feeds = {
    'scmp_hongkong': 'https://www.scmp.com/rss/2/feed',
    'scmp_business': 'https://www.scmp.com/rss/5/feed',
    'scmp_lifestyle': 'https://www.scmp.com/rss/322184/feed',
    'rthk_news': 'https://rthk.hk/rthk/news/rss/e_expressnews_elocal.xml',
    'rthk_business': 'https://rthk.hk/rthk/news/rss/e_expressnews_ebusiness.xml',
    'yahoo_hk': 'http://hk.news.yahoo.com/rss/hong-kong',
    'google_news_hk': 'http://news.google.com.hk/news?pz=1&cf=all&ned=hk&hl=zh-TW&output=rss',
    'chinadaily_hk': 'http://www.chinadaily.com.cn/rss/hk_rss.xml',
    'hkfp': 'https://www.hongkongfp.com/feed/',
    'hket_hk': 'https://www.hket.com/rss/hongkong',
    'hket_finance': 'https://www.hket.com/rss/finance',
    'hket_property': 'https://www.hket.com/rss/property',
}
```

### 3. Google Newsが香港無関係記事を多数返している
- `google_news_hk`が「トランプ」「Meta」などを返す
- フィルタリングが弱い

---

##  ✅ 解決策（3段階）

### 📌 解決策1: RSSソースを大幅に追加

```python
# 追加すべきRSSフィード
rss_feeds_additional = {
    # 主要メディア
    'thestandard': 'https://www.thestandard.com.hk/newsfeed/latest/news.xml',
    'mingpao': 'https://news.mingpao.com/rss/pns/s00002.xml',  # 明報
    'singtao': 'https://std.stheadline.com/rss/news.xml',  # 星島日報
    'oriental_daily': 'https://orientaldaily.on.cc/rss/news.xml',  # 東方日報
    'am730': 'https://www.am730.com.hk/rss/news.xml',
    'hk01_news': 'https://www.hk01.com/rss/article/local',  # 香港01
    
    # ビジネス専門
    'ejfq': 'https://www.ejfq.com/rss.xml',  # 信報
    'hkej': 'http://www1.hkej.com/rss/onlinenews.xml',
    
    # 政府・公式
    'gov_hk': 'https://www.news.gov.hk/rss/en/index.xml',
    
    # 文化・ライフスタイル
    'lifestyle_hk': 'https://www.scmp.com/rss/322184/feed',
    'timeout_hk': 'https://www.timeout.com/hong-kong/feed',
}
```

### 📌 解決策2: Google Newsのフィルタリング強化

```python
# Google Newsから取得した記事は香港関連度を厳格チェック
if source == 'google_news_hk':
    # 必須キーワードチェックを追加
    required_keywords = ['hong kong', 'hongkong', '香港', 'hk ']
    if not any(kw in content.lower() for kw in required_keywords):
        continue  # 除外
```

### 📌 解決策3: 処理済みURL履歴のクリア

```python
# 処理済みURLが古すぎる場合はクリア
# 現在: 永久に保存 → 変更: 7日以上古いURLは削除
```

---

## 🎯 期待される改善

### 改善前（現状）
```
取得数: 13件
香港関連: 3〜5件
記事の多様性: ❌（スポーツ偏重）
```

### 改善後
```
取得数: 80〜150件
香港関連: 60〜100件
記事の多様性: ✅（バランス良好）

カテゴリー例:
- ビジネス・経済: 15件
- 政治・行政: 12件
- 社会・その他: 10件
- テクノロジー: 8件
- 文化: 6件
- スポーツ: 2件（全国運動会は除外）
```

---

## 🚀 実装順序

1. **最優先**: RSSソースを10〜15個追加
2. **高優先**: Google Newsのフィルタリング強化
3. **中優先**: 処理済みURL履歴の有効期限設定（7日）


