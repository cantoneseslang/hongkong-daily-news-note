# ニュース記事フィルタリング問題の根本原因と解決策

## 🔴 問題点

### 問題1: 香港に関係ないニュースが多い
- 現状: すべてのニュースを取り込み、香港関連度チェックなし
- 例: オランダ政府、中国外交部、ロシア関連など

### 問題2: 同じ内容のニュースが3日間繰り返される
- 現状: 「全国運動会」のような長期イベントの記事が毎日複数選ばれる
- 原因: 
  - スポーツが「カルチャー」カテゴリーに含まれている（上限4件）
  - 全国運動会の記事は少しずつ違うため重複検出されない

---

## ✅ 解決策

### 1. 香港関連度フィルタリングを追加

**追加箇所**: ニュース初期フィルタリング段階（900行目付近）

```python
# 香港関連チェック
def is_hong_kong_related(news: Dict) -> bool:
    """ニュースが香港に関連しているかチェック"""
    title = news.get('title', '').lower()
    description = news.get('description', '').lower()
    content = f"{title} {description}"
    
    # 香港関連キーワード
    hk_keywords = [
        '香港', 'hong kong', 'hk', '立法会', '行政長官',
        'mtr', '九龍', 'kowloon', '新界', 'new territories',
        '香港島', 'hong kong island', '大埔', 'tai po',
        '屯門', 'tuen mun', '観塘', 'kwun tong'
    ]
    
    return any(keyword in content for keyword in hk_keywords)
```

### 2. スポーツカテゴリーを分離

**変更箇所**: カテゴリー分類ロジック（986行目）

```python
# 現在
elif any(keyword in content for keyword in ['文化', '芸能', 'スポーツ', ...]):
    category = 'カルチャー'

# ↓ 変更後
elif any(keyword in content for keyword in ['スポーツ', 'sports', '運動会', '試合', '選手', 'メダル', ...]):
    category = 'スポーツ'
elif any(keyword in content for keyword in ['文化', '芸能', '映画', '音楽', ...]):
    category = 'カルチャー'
```

### 3. カテゴリー上限の調整

**変更箇所**: カテゴリー上限設定（1024行目）

```python
category_limits = {
    'ビジネス・経済': 6,
    '社会・その他': 5,
    '政治・行政': 4,
    'テクノロジー': 4,
    'カルチャー': 3,  # 4 → 3 に削減
    'スポーツ': 2,     # 新規追加：上限2件
    '交通': 3,
    '不動産': 3,
    '事故・災害': 2,
    '治安・犯罪': 2,
    '医療・健康': 1,
    '教育': 1,
}
```

### 4. 全国運動会の記事制限

**追加箇所**: ニュース選択ロジック（1057行目の`select_news`関数内）

```python
# 全国運動会の記事を1日2件までに制限
national_games_count = 0
MAX_NATIONAL_GAMES = 2

for news in items:
    title = news.get('title', '').lower()
    
    # 全国運動会の記事チェック
    is_national_games = any(keyword in title for keyword in ['全国運動会', 'national games'])
    
    if is_national_games:
        if national_games_count >= MAX_NATIONAL_GAMES:
            continue
        national_games_count += 1
```

---

## 📊 期待される改善効果

### 改善前（現状）
```
20日の記事:
- オランダ政府のNexperia... ❌
- 中国外交部... ❌
- 全国運動会 × 5件 ❌
```

### 改善後
```
20日の記事:
- 香港関連のビジネス、経済、政治 ✅
- 香港の交通、不動産、社会 ✅
- 全国運動会は最大2件まで ✅
- スポーツは全体で2件まで ✅
```

---

## 🚀 実装優先度

1. **最優先**: 香港関連度フィルタリング（問題1を解決）
2. **高優先**: スポーツカテゴリー分離と上限設定（問題2を解決）
3. **中優先**: 全国運動会の記事制限（問題2の微調整）


