#!/usr/bin/env python3
"""
記事タイトルの重複分析スクリプト
"""
import re
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """URLを正規化"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return normalized
    except:
        return url

def normalize_title(t):
    """タイトルを正規化（小文字化、記号除去、単語分割）"""
    t = t.lower()
    t = re.sub(r'[^\w\s]', '', t)
    return set(t.split())

def calculate_title_similarity(title1: str, title2: str) -> float:
    """2つのタイトルの類似度を計算（0.0-1.0）"""
    words1 = normalize_title(title1)
    words2 = normalize_title(title2)
    
    if not words1 or not words2:
        return 0.0
    
    common_words = words1 & words2
    if len(common_words) < 3:
        return 0.0
    
    all_words = words1 | words2
    similarity = len(common_words) / len(all_words) if all_words else 0.0
    
    min_length = min(len(words1), len(words2))
    if min_length > 0:
        coverage = len(common_words) / min_length
        if similarity >= 0.6 and coverage >= 0.7:
            return similarity
    
    return 0.0

# 11/1の記事
articles_11_01 = [
    "米中貿易休戦、香港の輸出業者に確実性と安堵をもたらす",
    "ハロウィーンで中環が賑わい、ナイトライフ業界は活況を予想",
    "香港の放置された海辺の敷地、プライベートエクイティ企業MBKにより新たな命を吹き込まれる",
    "香港のポール・チャン財政長官、GDP3.8%増で経済は「順調」と発言",
    "「秘密のソース」が明らかに、ローズウッド香港が世界最高のホテルに選出",
    "香港の法廷弁護士が最高の行動規範を保つための「黄金律」とは",
    "米国、中国の第一段階貿易協定遵守状況を引き続き調査",
    "デロイト・チャイナ、香港で1,000人を雇用し6,400万米ドルを投資へ",
    "香港は「アジアのヨットクラブ」に加わる道筋をつけた。実現できるか？",
    "上水新田麒麟村の倉庫で三級火災、火勢は鎮圧されるも住民は猫や犬を心配し涙（更新）",
    "土地収用は長期的な解決策となるか？",
    "地区評議会選挙結果から学ぶべき重要な教訓"
]

# 11/2の記事
articles_11_02 = [
    "香港の財界トップや地域社会が全国運動会の聖火リレーに準備",
    "ローズウッド香港が世界最高のホテルに選出、「秘伝のソース」が明らかに",
    "米中貿易停戦が香港の輸出業者に確実性と安堵をもたらす",
    "ハロウィーンで中環が賑わい、ナイトライフ事業者は好景気を期待",
    "「雲端対談」第三シリーズ第四回：巨湾技研の裴鋒総裁に独占インタビュー（上）",
    "4つの巨大な空気注入式彫刻がビクトoriaハーバーを巡回する最終日、多くの市民が観覧",
    "大埔三門仔で78歳の躉船作業員が海に転落し死亡",
    "デロイト中国、香港で1000人を雇用し6400万米ドルを投資へ",
    "香港は「アジアのヨットクラブ」への道を歩む。その実現は可能か？",
    "タンザニア大統領選結果発表、現職ハッサン氏が高得票で当選",
    "土地収用は長期的な解決策となるか？",
    "区議会選挙結果から学ぶべき重要な教訓",
    "中国はあらゆる銀行危機に備えている",
    "全運会香港聖火ランナーリスト発表、香港卓球のエース黄鎮廷が第一走者",
    "中国と英国の警察、大規模な仮想通貨詐欺事件で資金回収のため協力",
    "香港立法会選挙の直接選挙議席を巡る競争が激化",
    "ビクトリアハーバー海上パレード｜サプライズ発表、4つの巨大な浮遊彫刻が明日登場",
    "香港、ノーザン・メトロポリスの資金調達にイスラム債発行を検討：ポール・チャン"
]

print("=" * 80)
print("記事タイトル重複分析")
print("=" * 80)
print()

print("【完全一致（正規化後）】")
print("-" * 80)
same_titles = []
for i, title1 in enumerate(articles_11_01, 1):
    normalized1 = re.sub(r'[^\w\s]', '', title1.lower())
    for j, title2 in enumerate(articles_11_02, 1):
        normalized2 = re.sub(r'[^\w\s]', '', title2.lower())
        if normalized1 == normalized2:
            same_titles.append((i, j, title1, title2))
            print(f"11/1 #{i} ↔ 11/2 #{j}: 完全一致")
            print(f"  11/1: {title1}")
            print(f"  11/2: {title2}")
            print()

print("【類似（類似度60%以上）】")
print("-" * 80)
similar_titles = []
for i, title1 in enumerate(articles_11_01, 1):
    for j, title2 in enumerate(articles_11_02, 1):
        # 既に完全一致として記録されているものはスキップ
        if any((i == si and j == sj) for si, sj, _, _ in same_titles):
            continue
        
        similarity = calculate_title_similarity(title1, title2)
        if similarity >= 0.6:
            similar_titles.append((i, j, title1, title2, similarity))
            print(f"11/1 #{i} ↔ 11/2 #{j}: 類似度 {similarity:.2%}")
            print(f"  11/1: {title1}")
            print(f"  11/2: {title2}")
            
            # 詳細分析
            words1 = normalize_title(title1)
            words2 = normalize_title(title2)
            common = words1 & words2
            print(f"  共通単語: {', '.join(sorted(common))}")
            print()

print("【新規記事（11/2のみ）】")
print("-" * 80)
new_articles = []
for j, title2 in enumerate(articles_11_02, 1):
    is_new = True
    normalized2 = re.sub(r'[^\w\s]', '', title2.lower())
    
    # 完全一致チェック
    for i, title1 in enumerate(articles_11_01, 1):
        normalized1 = re.sub(r'[^\w\s]', '', title1.lower())
        if normalized1 == normalized2:
            is_new = False
            break
    
    # 類似度チェック
    if is_new:
        for i, title1 in enumerate(articles_11_01, 1):
            similarity = calculate_title_similarity(title1, title2)
            if similarity >= 0.6:
                is_new = False
                break
    
    if is_new:
        new_articles.append((j, title2))
        print(f"11/2 #{j}: {title2}")

print()
print("=" * 80)
print("【統計】")
print("-" * 80)
print(f"完全一致: {len(same_titles)}件")
print(f"類似記事: {len(similar_titles)}件")
print(f"新規記事（11/2のみ）: {len(new_articles)}件")
print(f"重複率: {(len(same_titles) + len(similar_titles)) / len(articles_11_02) * 100:.1f}%")



