#!/usr/bin/env python3
"""
香港ニュース記事生成スクリプト（広東語学習セクション付き）
"""

import json
import os
import time
import requests
import re
import html
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse, urlunparse

try:
    from dateutil import parser as dateutil_parser
except ImportError:  # pragma: no cover - フォールバック用
    dateutil_parser = None

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))
SELECTED_NEWS_HISTORY_PATH = 'daily-articles/selected_news_history.json'
SELECTED_NEWS_HISTORY_RETENTION_DAYS = 14

EVENT_CHAR_NORMALIZATION = str.maketrans({
    '灣': '湾',
    '會': '会',
    '國': '国',
    '區': '区',
    '臺': '台',
    '學': '学',
    '醫': '医',
    '業': '业',
    '發': '発',
    '點': '点',
    '綫': '線',
    '綱': '網',
    '證': '証',
    '與': '与',
    '將': '将',
    '兩': '両',
    '這': '這',
    '馮': '冯',
    '陳': '陈',
    '鍾': '钟',
    '廣': '広',
    '東': '東',
    '號': '号',
})

EVENT_ALIAS_REPLACEMENTS = (
    ('香港ドル', 'hkd'),
    ('港元', 'hkd'),
    ('hk$', 'hkd'),
    ('hk$', 'hkd '),
    ('ｈｋ＄', 'hkd'),
    ('人民代表大会', '全人代'),
    ('全国人民代表大会', '全人代'),
    ('両会', '兩会'),
    ('兩會', '兩会'),
    ('粤港澳大湾区', '大湾区'),
    ('粵港澳大灣區', '大湾区'),
    ('粤港澳', '大湾区'),
    ('粵港澳', '大湾区'),
    ('玄関口', 'ゲートウェイ'),
    ('ゲートウェー', 'ゲートウェイ'),
    ('国際ハブ', 'グローバルハブ'),
    ('國際金融中心', '国際金融センター'),
    ('國際教育樞紐', '国際教育ハブ'),
    ('國際教育ハブ', '国際教育ハブ'),
    ('灣仔', '湾仔'),
    ('浸會大學', '香港浸会大学'),
    ('浸会大学', '香港浸会大学'),
    ('mpf年金', 'mpf'),
    ('積金易', '積金易'),
)

EVENT_GENERIC_TOKENS = {
    '香港', 'hong kong', 'hongkong', '中国', '北京', '政府', '香港政府', '中国政府',
    '香港01', '香港電台', '香港電台ニュース', '香港01ニュース', 'scmp', 'rthk', 'yahoo',
    '報道', 'ニュース', '最新', '速報', '分析', '情勢分析', '要請', '検討', '発表',
    '強化', '役割', '方針', '計画', '推進', '検討すべき', '記録', '本日', '今日',
    '香港人', '香港市民', '市民', '当局', '当局は', '代表者', '業界代表', '政府活動報告',
    '全国', '全国人民', '両会', '兩会', '全国両会', '全人代', '大湾区', '灣区', '大灣區',
    '国際', '香港立法会議員', '立法会議員', '元香港議員', '元香港立法会議員',
    'former lawmaker', 'hong kong lawmaker', 'hong kong', 'former hong kong lawmaker',
    'reported', 'says', 'said', 'urged', 'hong kongs', 'hongkongs', 'committee',
    'government', 'officials', 'official', 'market', 'report', 'representatives',
}

EVENT_STRONG_ASCII_TOKENS = {
    'mpf', 'ipo', 'hsbc', 'hkcec', 'byd', 'rthk', 'hkbu', 'legco', 'airtag',
}


def normalize_title_words(title: str) -> Set[str]:
    """タイトルを単語集合に正規化"""
    if not title:
        return set()
    normalized = re.sub(r'[^\w\s]', ' ', title.lower())
    words = {w for w in normalized.split() if len(w) > 1 or w.isdigit()}
    return words


def normalize_title_chars(title: str) -> str:
    """タイトルを文字単位で正規化（CJK重複検出用）"""
    if not title:
        return ""
    cleaned = re.sub(r'\s+', '', title.lower())
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', cleaned)
    return cleaned


def title_similarity_chars(a: str, b: str) -> float:
    """文字列ベースの類似度（SequenceMatcher）"""
    if not a or not b:
        return 0.0
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def _contains_keyword(text: str, keywords: List[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    for kw in keywords:
        if kw in text or kw in lowered:
            return True
    return False


def is_japan_related(title: str, description: str, url: str = "") -> bool:
    combined = f"{title} {description} {url}"
    keywords = [
        '日本', 'japan', '日本企業', '日本ブランド', '日本食', '和食', '寿司', 'ラーメン',
        '居酒屋', '和菓子', '抹茶', 'japanese', 'tokyo', 'osaka', 'kyoto',
        '無印良品', 'muji', 'ユニクロ', 'unqlo', 'uniqlo', 'ローソン', 'セブンイレブン',
        'ファミリーマート', 'すき家', '吉野家', 'くら寿司', 'はま寿司', '松屋', 'モスバーガー',
        'サントリー', 'キリン', 'アサヒ', '日経', '伊勢丹', '高島屋', 'パナソニック',
        'ソニー', '任天堂', 'トヨタ', 'ホンダ', '日産', 'ラーメン', '唐揚げ', '和牛'
    ]
    return _contains_keyword(combined, keywords)


def is_gba_related(title: str, description: str, url: str = "") -> bool:
    combined = f"{title} {description} {url}"
    keywords = [
        '大湾区', '大灣區', '粤港澳', '粵港澳', '粤港澳大湾区', '粵港澳大灣區', '珠三角',
        '広東省', '廣東省', '深セン', '深圳', 'shenzhen', 'guangdong', 'dongguan',
        '中山', '珠海', 'zhuhai', '前海', '南沙', '横琴', 'hong kong-zhuhai-macao bridge',
        'greater bay area', 'gba', '湾区経済', '湾区', '灣區', '佛山', 'foshan', '惠州',
        'huizhou', '江門', 'jiangmen', '肇慶', 'zhaoqing'
    ]
    return _contains_keyword(combined, keywords)


def is_fire_related(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    fire_keywords = [
        '火災', '火事', '火災後', '火災で', '火災に', '火災現場', '火災報', '火災避難',
        '大火', '火災死亡', '火災関連', '火災救助', '火災発生', '火災被害',
        'fire ', ' fire', 'fire-', 'fire:', 'fire.', 'fire,', 'firefighters', 'blaze',
        'inferno', 'conflagration'
    ]
    return any(kw in text for kw in fire_keywords)


def titles_are_similar(
    words_a: Set[str],
    words_b: Set[str],
    *,
    min_common: int = 2,
    min_similarity: float = 0.5,
    min_coverage: float = 0.6
) -> bool:
    """2つのタイトル語集合が十分に類似しているかを判定"""
    if not words_a or not words_b:
        return False

    shortest_len = min(len(words_a), len(words_b))
    dynamic_min_common = min_common
    if shortest_len <= 4:
        dynamic_min_common = max(2, shortest_len)

    common_words = words_a & words_b
    if len(common_words) < dynamic_min_common:
        return False

    all_words = words_a | words_b
    similarity = len(common_words) / len(all_words) if all_words else 0.0
    coverage = len(common_words) / shortest_len if shortest_len else 0.0

    return similarity >= min_similarity and coverage >= min_coverage


def is_similar_title_words(
    words: Set[str],
    existing_word_sets: List[Set[str]],
    *,
    min_common: int = 2,
    min_similarity: float = 0.5,
    min_coverage: float = 0.6
) -> bool:
    """既存タイトル集合との類似判定"""
    for existing in existing_word_sets:
        if titles_are_similar(
            words,
            existing,
            min_common=min_common,
            min_similarity=min_similarity,
            min_coverage=min_coverage,
        ):
            return True
    return False


def normalize_url(url: str) -> str:
    """URLを正規化（スキーム/ホスト/パスのみ）"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return normalized
    except Exception:
        return url


def sanitize_source_text(text: str) -> str:
    """RSS/スクレイプ由来のHTML残骸や壊れたリンク断片を除去"""
    if not text:
        return ""

    cleaned = html.unescape(text)
    cleaned = re.sub(r'(?is)<br\s*/?>', '\n', cleaned)
    cleaned = re.sub(r'(?is)<a\s+href=["\'][^"\']*["\'][^>]*>(.*?)</a>', r'\1', cleaned)
    cleaned = re.sub(r'(?is)<a\s+href=["\'][^"\']*["\'][^>]*>', ' ', cleaned)
    cleaned = re.sub(r'(?is)<a\s+href=[^>\s]+', ' ', cleaned)
    cleaned = re.sub(r'(?is)</a>', ' ', cleaned)
    cleaned = re.sub(r'(?is)<[^>]+>', ' ', cleaned)

    filtered_lines: List[str] = []
    for raw_line in cleaned.splitlines():
        line = re.sub(r'\s+', ' ', raw_line).strip()
        if not line:
            continue

        lowered = line.lower()
        if lowered in {'google news', 'google news hk'}:
            continue
        if 'comprehensive up-to-date news coverage' in lowered:
            continue
        if 'target="_blank"' in lowered or 'target=_blank' in lowered:
            continue
        if '<a href' in lowered or 'href=' in lowered:
            continue
        if re.fullmatch(r'[A-Za-z0-9_/\-+=]{40,}', line):
            continue

        filtered_lines.append(line)

    cleaned = '\n'.join(filtered_lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def has_suspicious_markup(text: str) -> bool:
    """note公開に不適切なHTML残骸・壊れたリンク断片を検出"""
    if not text:
        return False

    suspicious_patterns = [
        r'<a\s+href=',
        r'</a\b',
        r'<(?:p|div|span|font|li|ul|ol|strong|em)\b',
        r'target=["\']?_blank',
        r'(?m)^[A-Za-z0-9_/\-+=]{60,}$',
    ]
    return any(re.search(pattern, text, re.IGNORECASE | re.MULTILINE) for pattern in suspicious_patterns)


def normalize_event_text(text: str) -> str:
    """重複判定用のイベント文面を正規化"""
    if not text:
        return ""

    normalized = text.lower().translate(EVENT_CHAR_NORMALIZATION)
    for src, dest in EVENT_ALIAS_REPLACEMENTS:
        normalized = normalized.replace(src.lower(), dest.lower())
    normalized = re.sub(r'[【】「」『』（）()\[\]{}<>〈〉《》"\'、。・,:：;；!！?？/\\|]+', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _clean_event_token(token: str) -> str:
    token = normalize_event_text(token).strip(" -_")
    if not token:
        return ""
    if token in EVENT_GENERIC_TOKENS:
        return ""
    if token.isdigit():
        return ""

    cleaned = token
    for generic in EVENT_GENERIC_TOKENS:
        if cleaned == generic:
            return ""
        if len(cleaned) > len(generic) + 1 and generic in cleaned:
            cleaned = cleaned.replace(generic, '')
    cleaned = cleaned.strip(" -_")
    if len(cleaned) < 2 or cleaned in EVENT_GENERIC_TOKENS:
        return ""
    return cleaned


def extract_event_anchors(title: str, description: str = "") -> Set[str]:
    """イベント固有の金額・場所・キーワードを抽出"""
    combined = normalize_event_text(f"{title} {description}")
    if not combined:
        return set()

    candidates: List[str] = []

    numeric_patterns = [
        r'\d+(?:億\d+万|\億|\万)?\s*hkd',
        r'hkd\s*\d+(?:\.\d+)?(?:\s*(?:million|billion))?',
        r'\d+(?:億\d+万|\億|\万)?(?:人|件|歳|年|月|日|時間|小時|％|%|倍|台|棟|宗|名|港元)',
        r'\d+(?:\.\d+)?(?:million|billion|percent|%)',
    ]
    for pattern in numeric_patterns:
        candidates.extend(re.findall(pattern, combined))

    cjk_tokens = re.findall(r'[\u4e00-\u9fff]{2,12}', combined)
    ascii_tokens = re.findall(r'\b[a-z][a-z0-9\-]{2,}\b', combined)
    candidates.extend(cjk_tokens)
    candidates.extend(ascii_tokens)

    unique_tokens = []
    seen = set()
    for candidate in candidates:
        cleaned = _clean_event_token(candidate)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique_tokens.append(cleaned)

    def token_priority(token: str):
        has_digit = any(ch.isdigit() for ch in token)
        is_ascii = token.isascii()
        is_strong_ascii = token in EVENT_STRONG_ASCII_TOKENS
        return (
            1 if has_digit else 0,
            1 if is_strong_ascii else 0,
            1 if len(token) >= 6 else 0,
            len(token),
            token,
        )

    prioritized = sorted(unique_tokens, key=token_priority, reverse=True)
    return set(prioritized[:10])


def is_same_news_event(title_a: str, description_a: str, title_b: str, description_b: str = "") -> bool:
    """URLや表記が違っても、同じ出来事なら重複とみなす"""
    title_words_a = normalize_title_words(title_a)
    title_words_b = normalize_title_words(title_b)
    if title_words_a and title_words_b and titles_are_similar(
        title_words_a,
        title_words_b,
        min_common=2,
        min_similarity=0.45,
        min_coverage=0.6,
    ):
        return True

    title_chars_a = normalize_title_chars(title_a)
    title_chars_b = normalize_title_chars(title_b)
    chars_similarity = title_similarity_chars(title_chars_a, title_chars_b)
    if chars_similarity >= 0.82:
        return True

    anchors_a = extract_event_anchors(title_a, description_a)
    anchors_b = extract_event_anchors(title_b, description_b)
    if not anchors_a or not anchors_b:
        return False

    common = anchors_a & anchors_b
    if not common:
        return False

    numeric_common = {token for token in common if any(ch.isdigit() for ch in token)}
    descriptive_common = {token for token in common if len(token) >= 3 and not token.isdigit()}

    topic_a = derive_topic_key(title_a)
    topic_b = derive_topic_key(title_b)
    same_topic = bool(topic_a and topic_b and topic_a == topic_b)

    if numeric_common and descriptive_common:
        return True
    if same_topic and len(descriptive_common) >= 2:
        return True
    if len(descriptive_common) >= 3:
        return True
    if len(common) >= 3 and len(descriptive_common) >= 2:
        return True
    if descriptive_common and chars_similarity >= 0.65:
        return True
    if len(descriptive_common) >= 3 and chars_similarity >= 0.5:
        return True

    return False


TOPIC_STOPWORDS = {
    '香港', '政府', '香港政府', '香港警察', '政府本部', '最新', '速報', '天気', '天氣',
    'ニュース', '報道', '中国', '特区政府', '行政長官', '立法会', '香港立法会',
    '火災', '火事', '事故', '香港電台', '香港電台ニュース', '香港天文台'
}


def derive_topic_key(title: str) -> Optional[str]:
    """タイトルから主要トピック語を抽出（CJK優先）"""
    if not title:
        return None

    cjk_matches = re.findall(r'[\u4e00-\u9fff]{2,}', title)
    candidates = []
    for match in cjk_matches:
        if len(match) < 2:
            continue
        if any(sw == match for sw in TOPIC_STOPWORDS):
            continue
        if all(sw not in match for sw in TOPIC_STOPWORDS):
            candidates.append(match)
        else:
            # stopwordを除いた部分を候補にする
            cleaned = match
            for sw in TOPIC_STOPWORDS:
                cleaned = cleaned.replace(sw, '')
            cleaned = cleaned.strip()
            if len(cleaned) >= 2 and cleaned not in TOPIC_STOPWORDS:
                candidates.append(cleaned)

    if candidates:
        # 最長文字列を優先
        return max(candidates, key=len)

    # 英語系の固有名詞を抽出
    english_candidates = re.findall(r'[A-Za-z][A-Za-z\s\-\']{3,}', title)
    english_candidates = [
        re.sub(r'\s+', ' ', cand.strip()).lower()
        for cand in english_candidates
        if cand.strip().lower() not in TOPIC_STOPWORDS
    ]
    if english_candidates:
        return max(english_candidates, key=len)

    return None


def get_recent_topics(days: int = 3) -> Dict[str, int]:
    """過去N日間の頻出トピックを取得"""
    try:
        from collections import Counter
        
        topic_counter = Counter()
        today = datetime.now(HKT)
        
        # トピックキーワードパターン
        topic_patterns = {
            '全国運動会': [r'全国運動会|National Games|全運會|NG|national games'],
            '立法会選挙': [r'立法会選挙|LegCo election|立法會選舉|district council'],
            '施政報告': [r'施政報告|Policy Address|policy address'],
            '失業率': [r'失業率|unemployment rate|jobless'],
            'GDP': [r'GDP|経済成長|economic growth|gross domestic'],
            'オリンピック': [r'オリンピック|Olympics|olympic'],
            '台風': [r'台風|Typhoon|typhoon|tropical storm'],
            '不動産価格': [r'不動産価格|property prices|housing prices|home prices'],
        }
        
        for i in range(1, days + 1):
            target_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            article_file = f'daily-articles/hongkong-news_{target_date}.md'
            
            if os.path.exists(article_file):
                try:
                    with open(article_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for topic, patterns in topic_patterns.items():
                        for pattern in patterns:
                            try:
                                if re.search(pattern, content, re.IGNORECASE):
                                    topic_counter[topic] += 1
                                    break  # 1記事につき1回カウント
                            except Exception:
                                pass
                except Exception:
                    pass
        
        return dict(topic_counter)
    except Exception:
        # エラー時は空の辞書を返す
        return {}


def is_overused_topic(title: str, description: str, recent_topics: Dict[str, int], threshold: int = 2) -> bool:
    """タイトル/説明が過去N日間で頻出トピック（2回以上）に該当するか"""
    try:
        if not recent_topics:
            return False
        
        content = f"{title} {description}".lower()
        
        for topic, count in recent_topics.items():
            try:
                if topic == '全国運動会' and count >= threshold:
                    if re.search(r'全国運動会|national games|全運會|\bng\b', content, re.IGNORECASE):
                        return True
                elif topic == '立法会選挙' and count >= (threshold + 2):
                    # 過度に排除しないため閾値を引き上げ
                    if re.search(r'立法会選挙|legco election|立法會選舉|district council', content, re.IGNORECASE):
                        return True
                elif topic == '施政報告' and count >= (threshold + 1):
                    if re.search(r'施政報告|policy address', content, re.IGNORECASE):
                        return True
            except Exception:
                continue
        
        return False
    except Exception:
        # エラー時は過剰トピックではないと判定
        return False


def parse_published_at(value: Optional[str]) -> Optional[datetime]:
    """公開日時文字列をHKTタイムゾーンのdatetimeに変換"""
    if not value:
        return None

    # 既にISO形式の場合を想定
    try:
        if dateutil_parser:
            dt = dateutil_parser.parse(value)
        else:
            dt = datetime.fromisoformat(value)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    try:
        return dt.astimezone(HKT)
    except Exception:
        return dt


def load_recent_selected_news(days: int = 3, history_path: str = SELECTED_NEWS_HISTORY_PATH) -> List[Dict]:
    """過去N日分の採用済み raw ニュース履歴を取得"""
    history_file = Path(history_path)
    if not history_file.exists():
        return []

    try:
        data = json.loads(history_file.read_text(encoding='utf-8'))
    except Exception:
        return []

    days_map = data.get('days', {})
    if not isinstance(days_map, dict):
        return []

    today = datetime.now(HKT)
    recent_items: List[Dict] = []
    for i in range(1, days + 1):
        day_key = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        raw_items = days_map.get(day_key, [])
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            recent_items.append(item)

    return recent_items


def save_selected_news_history(
    selected_news: List[Dict],
    *,
    history_path: str = SELECTED_NEWS_HISTORY_PATH,
    target_date: Optional[str] = None,
):
    """当日採用した raw ニュースを履歴として保存"""
    history_file = Path(history_path)
    history_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        if history_file.exists():
            data = json.loads(history_file.read_text(encoding='utf-8'))
        else:
            data = {}
    except Exception:
        data = {}

    days_map = data.get('days', {})
    if not isinstance(days_map, dict):
        days_map = {}

    date_key = target_date or datetime.now(HKT).strftime('%Y-%m-%d')
    normalized_items = []
    for item in selected_news:
        if not isinstance(item, dict):
            continue
        normalized_items.append({
            'title': item.get('title', ''),
            'description': item.get('description', ''),
            'url': item.get('url', ''),
            'source': item.get('source', ''),
            'published_at': item.get('published_at') or item.get('published') or item.get('publishedAt') or '',
        })

    days_map[date_key] = normalized_items

    cutoff = datetime.now(HKT) - timedelta(days=SELECTED_NEWS_HISTORY_RETENTION_DAYS)
    pruned_days = {}
    for key, value in days_map.items():
        try:
            day_dt = datetime.strptime(key, '%Y-%m-%d').replace(tzinfo=HKT)
        except Exception:
            continue
        if day_dt >= cutoff:
            pruned_days[key] = value

    output = {
        'last_updated': datetime.now(HKT).isoformat(),
        'days': pruned_days,
    }
    history_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')

class GrokArticleGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # API選択（Gemini → Claude → Grok の順でフォールバック）
        if 'gemini_api' in self.config and self.config['gemini_api'].get('api_key'):
            self.api_key = self.config['gemini_api']['api_key']
            self.api_url = self.config['gemini_api']['api_url']
            self.use_gemini = True
        elif 'claude_api' in self.config and self.config['claude_api'].get('api_key'):
            self.api_key = self.config['claude_api']['api_key']
            self.api_url = self.config['claude_api']['api_url']
            self.use_gemini = False
        else:
            # Grok APIをデフォルト使用
            self.api_key = self.config['grok_api']['api_key']
            self.api_url = self.config['grok_api']['api_url']
            self.use_gemini = None
        
        self.grok_model = (
            self.config.get('grok_api', {}).get('model')
            or os.environ.get('GROK_MODEL')
            or 'grok-3'
        )
        
    def generate_article(self, news_data: List[Dict]) -> Dict:
        """Gemini/Claude/Grok APIで日本語記事を生成"""
        if self.use_gemini is True:
            api_name = "Google Gemini"
        elif self.use_gemini is False:
            api_name = "Claude API"
        else:
            api_name = "Grok API"
        print(f"\n🤖 {api_name}で記事生成中...")
        print("=" * 60)
        
        # ニュースデータを整形
        news_text = self._format_news_for_prompt(news_data)
        
        # 今日の日付を取得（HKTタイムゾーン）
        today_date = datetime.now(HKT).strftime('%Y年%m月%d日')
        today_date_iso = datetime.now(HKT).strftime('%Y-%m-%d')
        
        # システムプロンプト
        system_prompt = """あなたは香港のニュースを日本語に翻訳し、記事を生成する専門家です。

翻訳ルール：
- すべてのテキストを自然な日本語に翻訳
- 香港の地名、人名、組織名は適切に翻訳
- ニュースの内容を正確に伝える
- 読みやすい記事形式で構成

記事構成：
- 各ニュースを### 見出しで区切る
- 内容を詳しく翻訳
- 引用元、リンク、備考を適切に配置
- 広告や宣伝文は除外

引用情報の形式（重要）：
各ニュースの最後に必ず以下の形式で記載してください：

**引用元**: ソース名（例：SCMP、RTHK、香港01等）
**リンク**: 完全なURL

例：
**引用元**: SCMP
**リンク**: https://www.scmp.com/news/hong-kong/law-and-crime/article/3330816/hong-kongs-scameter-app-gets-upgrade-ai-tools-tackle-social-media-scams

重要：JSON形式ではなく、Markdown形式で記事を生成してください。引用元とリンクは必ず別々の行に記載し、**で囲んでください。"""

        # ユーザープロンプト
        user_prompt = f"""以下の香港ニュースを日本語に翻訳し、記事として構成してください：

【重要】今日の日付は {today_date}（{today_date_iso}）です。タイトルには必ず「毎日AI香港ピックアップニュース({today_date})」という形式を使用してください。

{news_text}

記事の要件：
1. タイトルは必ず「# 毎日AI香港ピックアップニュース({today_date})」という形式で記載してください
2. 各ニュースを### 見出しで区切る
3. 内容を詳しく翻訳
4. 引用元、リンク、備考を適切に配置
5. 広告や宣伝文は除外
6. Markdown形式で出力

引用情報の形式（重要）：
各ニュースの最後に必ず以下の形式で記載してください：

**引用元**: ソース名（例：SCMP、RTHK、香港01等）
**リンク**: 完全なURL

例：
**引用元**: SCMP
**リンク**: https://www.scmp.com/news/hong-kong/law-and-crime/article/3330816/hong-kongs-scameter-app-gets-upgrade-ai-tools-tackle-social-media-scams

重要：引用元とリンクは必ず別々の行に記載し、**で囲んでください。

記事を生成してください："""

        # APIリクエスト（Gemini/Claude/Grok対応）
        if self.use_gemini is True:
            # Gemini API
            headers = {
                "Content-Type": "application/json"
            }
            # APIキーをURLパラメータに追加
            api_url_with_key = f"{self.api_url}?key={self.api_key}"
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"{system_prompt}\n\n{user_prompt}"
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 50000
                }
            }
        else:
            # Claude/Grok API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            if self.use_gemini is False:  # Claude API
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "messages": [
                        {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 50000
                }
            else:  # Grok API
                payload = {
                    "model": self.grok_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 50000
                }
        
        if self.use_gemini is True:
            print("📤 Google Geminiにリクエスト送信中...")
        elif self.use_gemini is False:
            print("📤 Claude APIにリクエスト送信中...")
        else:
            print("📤 Grok APIにリクエスト送信中...")
        
        try:
            # Gemini APIの場合はURLにAPIキーを追加
            url = api_url_with_key if self.use_gemini is True else self.api_url
            # Google / LLM 側が応答を返さず切断する場合がある（GitHub Actions 等）→ 再試行
            _retries = max(1, int(os.environ.get("LLM_HTTP_RETRIES", "5")))
            _transient = (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
            )
            response = None
            for attempt in range(1, _retries + 1):
                try:
                    response = requests.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=300,
                    )
                    break
                except _transient as e:
                    if attempt >= _retries:
                        raise
                    wait = min(2 ** (attempt - 1), 60)
                    print(
                        f"⚠️ 接続が切れました（{attempt}/{_retries}）: {e!s}\n"
                        f"   {wait}秒待って再試行します…"
                    )
                    time.sleep(wait)
            if response is None:
                raise RuntimeError("LLM HTTP: response is None after retries")
            
            if response.status_code == 200:
                result = response.json()
                
                if self.use_gemini is True:
                    # Gemini APIレスポンス
                    content = result['candidates'][0]['content']['parts'][0]['text']
                else:
                    # Claude/Grok APIレスポンス
                    if self.use_gemini is False:  # Claude API
                        content = result['content'][0]['text']
                    else:  # Grok API
                        content = result['choices'][0]['message']['content']
                
                print("✅ 記事生成完了")
                
                # 記事をパースして構造化
                article = self._parse_article_content(content)
                article["body"] = self._ensure_section_count(article["body"], news_data)
                return article
                
            else:
                print(f"❌ APIエラー: {response.status_code}")
                print(f"   詳細: {response.text}")
                
                # Gemini APIが地域制限の場合はGrok APIにフォールバック
                if (response.status_code == 403 or response.status_code == 400) and self.use_gemini is True:
                    print("🔄 Gemini API地域制限のためGrok APIにフォールバック...")
                    return self._fallback_to_grok(news_data)
                
                # Grok APIがクレジット切れの場合はClaude APIにフォールバック
                if response.status_code == 429 and self.use_gemini is None:
                    print("🔄 Grok APIクレジット切れのためClaude APIにフォールバック...")
                    return self._fallback_to_claude(news_data)

                # Grok APIの一時障害系はClaude APIにフォールバック
                if response.status_code >= 500 and self.use_gemini is None:
                    print("🔄 Grok APIサーバーエラーのためClaude APIにフォールバック...")
                    return self._fallback_to_claude(news_data)
                
                return None
                
        except Exception as e:
            print(f"❌ 例外発生: {e}")
            # Gemini が切断・タイムアウト等で失敗したら Grok にフォールバック（設定がある場合）
            if self.use_gemini is True and self.config.get("grok_api", {}).get("api_key"):
                print("🔄 Gemini API 例外のため Grok API にフォールバック...")
                return self._fallback_to_grok(news_data)
            if self.use_gemini is None:
                print("🔄 Grok API例外のためClaude APIにフォールバック...")
                return self._fallback_to_claude(news_data)
            return None
    
    def _fallback_to_grok(self, news_data: List[Dict]) -> Dict:
        """Grok APIにフォールバック"""
        print("🔄 Grok APIで記事生成中...")
        
        # Grok APIの設定
        self.api_key = self.config['grok_api']['api_key']
        self.api_url = self.config['grok_api']['api_url']
        self.use_gemini = None
        self.grok_model = (
            self.config.get('grok_api', {}).get('model')
            or os.environ.get('GROK_MODEL')
            or 'grok-3'
        )
        
        # 元のgenerate_articleメソッドを再帰呼び出し
        return self.generate_article(news_data)
    
    def _fallback_to_claude(self, news_data: List[Dict]) -> Dict:
        """Claude APIにフォールバック"""
        print("🔄 Claude APIで記事生成中...")
        
        # Claude APIの設定
        self.api_key = self.config['claude_api']['api_key']
        self.api_url = self.config['claude_api']['api_url']
        self.use_gemini = False
        
        # 元のgenerate_articleメソッドを再帰呼び出し
        return self.generate_article(news_data)
    
    def _parse_article_content(self, content: str) -> Dict:
        """生成された記事コンテンツをパース"""
        # タイトルを抽出（最初の行）
        lines = content.split('\n')
        title = lines[0].replace('#', '').strip() if lines else "香港ニュース"
        
        # 本文を抽出（タイトル行を除く）
        if lines and lines[0].startswith('#'):
            body = '\n'.join(lines[1:])
        else:
            body = content
        
        return {
            "title": title,
            "lead": "",
            "body": body,
            "tags": "香港,広東語,廣東話,中国語ニュース,最新,情報,アジア"
        }
    
    def _format_news_for_prompt(self, news_data: List[Dict]) -> str:
        """ニュースデータをプロンプト用に整形"""
        formatted = []
        for i, news in enumerate(news_data, 1):
            title = sanitize_source_text(news.get('title', ''))
            description = sanitize_source_text(news.get('description', ''))
            url = news.get('url', '')
            source = news.get('source', '')
            published = news.get('published_at') or news.get('published', '')
            
            formatted.append(f"""
ニュース {i}:
タイトル: {title}
内容: {description}
URL: {url}
ソース: {source}
公開日時: {published}
""")
        
        return '\n'.join(formatted)
    
    def format_weather_info(self, weather_data: Dict) -> str:
        """天気情報をMarkdown形式に整形"""
        if weather_data is None:
            return ""
        
        import re
        
        def clean_weather_text(text: str) -> str:
            """天気情報のテキストをクリーンアップ"""
            if not text:
                return ""
            # HTMLタグを改行に変換
            text = re.sub(r'<br\s*/?>', '\n', text)
            # 他のHTMLタグを除去
            text = re.sub(r'<[^>]+>', '', text)
            # 各行ごとに処理
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                # 行内の連続する空白を1つに
                line = re.sub(r'\s+', ' ', line).strip()
                if line:
                    cleaned_lines.append(line)
            return '\n'.join(cleaned_lines)
        
        weather_section = "## 本日の香港の天気\n"
        has_content = False
        
        # 天気警報
        if weather_data.get('weather_warning'):
            warning = weather_data['weather_warning']
            title = warning.get('title', 'N/A')
            desc = clean_weather_text(warning.get('description', ''))
            
            if title and "現時並無警告生效" not in title and "酷熱天氣警告" not in title and "發出" not in title:
                weather_section += f"\n### 天気警報\n{title}\n"
                if desc and "現時並無警告生效" not in desc and "酷熱天気警告" not in desc:
                    weather_section += f"{desc}\n"
                has_content = True
        
        # 地域天気予報のみ表示
        if weather_data.get('weather_forecast'):
            forecast = weather_data['weather_forecast']
            title = forecast.get('title', 'N/A')
            desc = clean_weather_text(forecast.get('description', ''))
            
            # 天気情報はLLMで一括日本語翻訳（辞書置換は使わない）
            # タイトルと本文を分けて翻訳
            if title and title != 'N/A':
                translated_title = self._llm_translate_text(title)
            else:
                translated_title = ""
            
            if desc:
                translated_desc = self._llm_translate_text(desc)
            else:
                translated_desc = ""
            
            # 天気予報セクションを構築
            weather_section += "\n### 天気予報\n"
            if translated_title:
                weather_section += f"{translated_title}\n\n"
            if translated_desc:
                weather_section += f"{translated_desc}\n"
            weather_section += "\n**引用元**: 香港天文台"
            has_content = True

        if not has_content:
            weather_section += "\n現在、天気情報を取得できませんでした。後ほど更新予定です。\n"
        
        return weather_section
    
    def _translate_weather_text(self, text: str) -> str:
        """レガシー互換（未使用）。LLMベース翻訳に切替済み。"""
        return self._llm_translate_text(text)

    def _llm_translate_text(self, text: str) -> str:
        """LLMで広東語/中文を自然な日本語に一発翻訳（日本語以外混在禁止）"""
        if not text:
            return ""
        
        # テキストが長すぎる場合は分割して翻訳
        max_chunk_length = 1000
        if len(text) > max_chunk_length:
            # まず改行で分割を試み、さらに長すぎる行は固定長で分割する
            def split_into_chunks(raw: str) -> List[str]:
                chunks: List[str] = []
                buffer = ""
                
                for line in raw.split('\n'):
                    # 行自体が長すぎる場合は固定長で分割
                    while len(line) > max_chunk_length:
                        chunks.append(line[:max_chunk_length])
                        line = line[max_chunk_length:]
                    
                    tentative = (buffer + "\n" + line) if buffer else line
                    if len(tentative) > max_chunk_length and buffer:
                        chunks.append(buffer)
                        buffer = line
                    else:
                        buffer = tentative
                
                if buffer:
                    chunks.append(buffer)
                
                # 念のため固定長での再分割（改行が全く無いテキストにも対応）
                normalized: List[str] = []
                for chunk in chunks:
                    if len(chunk) <= max_chunk_length:
                        normalized.append(chunk)
                    else:
                        for i in range(0, len(chunk), max_chunk_length):
                            normalized.append(chunk[i:i + max_chunk_length])
                return normalized
            
            translated_chunks = [
                self._llm_translate_text(chunk)
                for chunk in split_into_chunks(text)
            ]
            return "\n".join(translated_chunks)
        
        prompt = (
            "以下の広東語/中文/英語テキストを完全に自然な日本語に翻訳してください。\n\n"
            "【重要な翻訳ルール】\n"
            "1. すべてのテキストを日本語に翻訳すること（英語、広東語、中国語が残らないように）\n"
            "2. 数値、記号、日付、時刻はそのまま保持すること\n"
            "3. 地名、人名、組織名は適切に日本語表記すること\n"
            "4. 専門用語は適切な日本語訳を使用すること\n"
            "5. 文章が途中で切れないよう、完全な文章として翻訳すること\n"
            "6. 翻訳結果には日本語のみを含め、他の言語（英語、中国語、広東語）を一切含めないこと\n\n"
            "原文:\n" + text + "\n\n"
            "日本語訳:"
        )

        try:
            if self.use_gemini is True:
                headers = {"Content-Type": "application/json"}
                api_url_with_key = f"{self.api_url}?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
                }
                resp = requests.post(api_url_with_key, headers=headers, json=payload, timeout=120)
                if resp.status_code == 200:
                    txt = resp.json()['candidates'][0]['content']['parts'][0]['text']
                    # "日本語訳:" で始まる場合は除去
                    if txt.startswith("日本語訳:"):
                        txt = txt[6:].strip()
                    return txt.strip()
                else:
                    print(f"⚠️  天気翻訳エラー (Gemini): HTTP {resp.status_code}")
                    print(f"    レスポンス: {resp.text[:200]}")
            else:
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                if self.use_gemini is False:
                    payload = {
                        "model": "claude-3-5-sonnet-20241022",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 4096,
                    }
                else:
                    payload = {
                        "model": self.grok_model,
                        "messages": [
                            {"role": "system", "content": "あなたは優秀な翻訳者です。広東語、中国語、英語を完全に自然な日本語に翻訳してください。原文の言語が残らないように注意してください。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 4096,
                    }
                resp = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
                if resp.status_code == 200:
                    if self.use_gemini is False:
                        txt = resp.json()['content'][0]['text']
                    else:
                        txt = resp.json()['choices'][0]['message']['content']
                    # "日本語訳:" で始まる場合は除去
                    if txt.startswith("日本語訳:"):
                        txt = txt[6:].strip()
                    return txt.strip()
                else:
                    print(f"⚠️  天気翻訳エラー (Claude/Grok): HTTP {resp.status_code}")
                    print(f"    レスポンス: {resp.text[:200]}")
        except Exception as e:
            print(f"⚠️  天気翻訳エラー (例外): {e}")
            import traceback
            traceback.print_exc()
        # フォールバック: 原文を返却（少なくとも欠落しない）
        print(f"⚠️  天気翻訳フォールバック: 原文を返却")
        return text
    
    def _ensure_section_count(self, body: str, news_data: List[Dict]) -> str:
        """生成本文を検証し、不正マークアップや欠落時はフォールバック生成"""
        expected_count = len(news_data)
        if expected_count == 0:
            return body

        section_count = len(re.findall(r'(?m)^###\s', body))
        invalid_markup = has_suspicious_markup(body)
        if section_count >= expected_count and not invalid_markup:
            return body

        reasons = []
        if section_count < expected_count:
            reasons.append(f"記事数不足 ({section_count}/{expected_count})")
        if invalid_markup:
            reasons.append("HTML残骸/壊れたリンク断片を検出")
        print(f"⚠️  生成本文の安全性検証に失敗: {', '.join(reasons)}。フォールバック生成を実行します。")

        # 既存本文の冒頭（最初の見出し以前）を保持
        first_heading_index = body.find("### ")
        prefix = body[:first_heading_index].strip() if first_heading_index > 0 else ""

        fallback_body = self._build_sections_from_news(news_data)
        fallback_sections = fallback_body.strip()

        combined = []
        if prefix:
            combined.append(prefix)
        combined.append(fallback_sections)

        final_body = "\n\n".join(part for part in combined if part)
        final_count = len(re.findall(r'(?m)^###\s', final_body))
        if final_count < expected_count:
            print(f"⚠️  フォールバック生成でも記事数が不足 ({final_count}/{expected_count})。")
        else:
            print(f"✅ フォールバック生成で {final_count} 件の記事を出力しました。")
        return final_body

    def _build_sections_from_news(self, news_data: List[Dict]) -> str:
        """ニュースデータから確実に件数分のMarkdownセクションを生成"""
        sections: List[str] = []
        for idx, news in enumerate(news_data, 1):
            source = news.get('_source') or news.get('source') or 'Unknown'
            url = news.get('url', '').strip()

            raw_title = sanitize_source_text((news.get('title') or f"ニュース {idx}").strip())
            translated_title = sanitize_source_text(self._llm_translate_text(raw_title)).strip() or raw_title

            summary_source = sanitize_source_text((news.get('full_content') or news.get('description') or "").strip())
            if len(summary_source) > 1500:
                summary_source = summary_source[:1500]
            translated_summary = sanitize_source_text(self._llm_translate_text(summary_source)).strip() if summary_source else ""

            section_lines = [f"### {translated_title}"]
            if translated_summary:
                section_lines.append(translated_summary)
            if source:
                section_lines.append(f"**引用元**: {source}")
            if url:
                section_lines.append(url)

            sections.append("\n\n".join(section_lines).strip())

        return "\n\n\n".join(sections)
    
    def _generate_cantonese_section(self) -> str:
        """広東語学習者向けの定型文を生成（固定内容・変更禁止）"""
        # この定型文は記事の最後に必ず追加される固定内容です
        # 内容を変更しないでください
        return """## 広東語学習者向け情報

広東語学習者向けにLINEが良い、便利という方もいるでしょうから、スラング先生公式アカウントもありますのでこちらご登録してから使用してください。秘書のリーさんが広東語についてなんでも回答してくれますのでぜひ使ってみてください

(今現在400名以上の方に登録していただいております）

[スラング先生LINE公式アカウント](https://line.me/R/ti/p/@298mwivr)

## 広東語| 広東語超基礎　超簡単！初めての広東語「9声6調」

https://youtu.be/RAWZAJUrvOU?si=WafOkQixyLiwMhUW"""
    
    def remove_advertisement_content(self, body: str) -> str:
        """記事本文から広告・宣伝コンテンツを除去"""
        import re
        
        # 広告・宣伝のキーワードパターン
        ad_patterns = [
            r'最新の動画紹介：.*?【詳細と申し込み】',
            r'TOPick.*?チャンネル.*?フォロー.*?見逃さないでください',
            r'無料の.*?会員.*?今すぐ.*?ダウンロード',
            r'会員新規募集.*?プレゼント.*?詳細：',
            r'https://whatsapp\.com/channel/.*?',
            r'https://onelink\.to/.*?',
            r'https://event\.hket\.com/.*?',
            r'【詳細と申し込み】',
            r'申し込み受付中',
            r'フォローして.*?見逃さないでください',
            r'ダウンロード：.*?',
            r'プレゼント.*?詳細：.*?',
            r'🔔.*?フォロー',
            r'無料.*?会員.*?参加しましょう',
            r'新規会員登録.*?プレゼント',
            # 広告記事の除外パターン
            r'この記事は広告パートナーによって制作されたものであり.*?翻訳しません。',
            r'広告パートナーによって制作された.*?広告や宣伝文は除外',
            r'presented.*?news.*?広告',
            r'スポンサー記事',
            r'広告記事',
            r'PR記事',
            r'presented.*?content'
        ]
        
        # 不要なテキストパターン（AIが自動生成する不要なテキスト）
        unwanted_patterns = [
            r'### 次のニュースはありません。',
            r'### 次のニュース.*?',
            r'### 以上.*?',
            r'### 終了.*?',
            r'### 記事は以上です。',
            r'### 以上が.*?ニュースです。',
            r'### 以上で.*?ニュースを終了します。'
        ]
        
        # 引用元とリンクの表示を修正するパターン
        fix_patterns = [
            # 引用元とリンクが一行にまとまっている場合を修正
            (r'\*\*引用元\*\*:\s*([^*]+)\*\*\*リンク\*\*:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元とリンクが*で囲まれている場合を修正
            (r'\*引用元:\s*([^*]+)\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元とリンクが*で囲まれている場合を修正（別パターン）
            (r'\*引用元:\s*([^*]+)\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMPリンク: URL の形式を修正
            (r'引用元:\s*([^\s]+)リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMPリンク: URL の形式を修正（スペースなし）
            (r'引用元:\s*([^:]+):\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMP**リンク: URL の形式を修正
            (r'引用元:\s*([^*]+)\*\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMP*リンク: URL の形式を修正
            (r'引用元:\s*([^*]+)\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMP*リンク: URL の形式を修正（スペースなし）
            (r'引用元:\s*([^*]+)\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMPリンク: [URL](URL) → 引用元行 + URL独立行
            (r'引用元:\s*([^\s]+)リンク:\s*\[((?:https?|ftp)://[^\]]+)\]\(([^\)]+)\)', r'**引用元**: \1\n\n\3'),
            # 引用元とリンクが同一行（[]()付き・太字でない）→ 引用元行 + URL独立行
            (r'引用元:\s*([^\n]+?)\s*リンク:\s*\[([^\]]+)\]\(([^\)]+)\)', r'**引用元**: \1\n\n\3'),
            # 引用元: SCMP**リンク: URL の形式を修正（スペースなし）
            (r'引用元:\s*([^*]+)\*\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # 引用元: SCMP*リンク: URL の形式を修正（スペースなし）
            (r'引用元:\s*([^*]+)\*リンク:\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2'),
            # HTML段落で出力された引用情報をMarkdown2行に正規化
            (r'<p[^>]*>\s*<strong>引用元</strong>:\s*([^<]+)<br\s*/?>\s*<strong>リンク</strong>:\s*(https?://[^\s<]+)\s*</p>', r'**引用元**: \1\n**リンク**: \2'),
            # strongタグ混在の単行表記を正規化
            (r'<strong>引用元</strong>:\s*([^<]+)\s*<strong>リンク</strong>:\s*(https?://[^\s<]+)', r'**引用元**: \1\n**リンク**: \2')
        ]

        # HTML残骸の削除（汎用）
        html_cleanup_patterns = [
            r'<p[^>]*>\s*</p>',                 # 空のp
            r'</?br\s*/?>',                    # brタグ
            r'(?im)^\s*<a\s+href=.*$',         # 壊れたaタグ開始行
            r'(?im)^\s*[A-Za-z0-9_/\-+=]{40,}\s*$',  # href断片/opaque token
            # [![...]](...) を包む p/span ハイライトを剥がす
            r'<p[^>]*>\s*<span[^>]*>(\[!\[.*?\]\(.*?\)\]\(.*?\))\s*</span>\s*</p>'
        ]
        
        # 広告コンテンツを除去
        cleaned_body = body
        for pattern in ad_patterns:
            cleaned_body = re.sub(pattern, '', cleaned_body, flags=re.DOTALL | re.IGNORECASE)
        
        # 不要なテキストを除去
        for pattern in unwanted_patterns:
            cleaned_body = re.sub(pattern, '', cleaned_body, flags=re.DOTALL | re.IGNORECASE)
        
        # 引用元とリンクの表示を修正
        for pattern, replacement in fix_patterns:
            cleaned_body = re.sub(pattern, replacement, cleaned_body, flags=re.DOTALL | re.IGNORECASE)

        # 汎用HTMLタグの掃除（必要最小限）
        for pattern in html_cleanup_patterns:
            # ラッパー除去パターンには置換対象を残す
            if '(' in pattern and '\\[!\\[' in pattern:
                cleaned_body = re.sub(pattern, r'\1', cleaned_body, flags=re.DOTALL | re.IGNORECASE)
            else:
                cleaned_body = re.sub(pattern, '', cleaned_body, flags=re.DOTALL | re.IGNORECASE)

        # note側の自動リンク化に任せるため、URLはプレーンで独立行にする
        # **リンク**: [text](url) → 空行 + url
        cleaned_body = re.sub(r'\*\*リンク\*\*:\s*\[[^\]]+\]\((https?://[^\)]+)\)', r'\n\n\1', cleaned_body)
        # **リンク**: url → 空行 + url
        cleaned_body = re.sub(r'\*\*リンク\*\*:\s*(https?://\S+)', r'\n\n\1', cleaned_body)
        # リンク: url → 空行 + url
        cleaned_body = re.sub(r'(?m)^リンク:\s*(https?://\S+)', r'\n\n\1', cleaned_body)
        # Google News系の残骸行を除去
        cleaned_body = re.sub(r'(?im)^\s*Google News(?: HK)?\s*$', '', cleaned_body)
        cleaned_body = re.sub(r'(?im)^.*Comprehensive up-to-date news coverage.*$', '', cleaned_body)
        
        # 行末の余分なスペースを除去（改行前の2スペースなど）
        cleaned_body = re.sub(r'[ \t]+$', '', cleaned_body, flags=re.MULTILINE)

        # 連続重複する引用ブロックを1つに圧縮（URL独立行対応）
        cleaned_body = re.sub(r'(\*\*引用元\*\*: .*?\n+https?://\S+)\n+\1', r'\1', cleaned_body, flags=re.DOTALL)

        # 広東語学習セクションの重複行を1回に圧縮（画像リンク2種）
        cantonese_img1 = re.escape('[![スラング先生公式LINE](https://raw.githubusercontent.com/cantoneseslang/hongkong-daily-news-note/main/shared/line-img1.jpg)](https://line.me/R/ti/p/@298mwivr)')
        cantonese_img2 = re.escape('[![LINEでお問合せ](https://raw.githubusercontent.com/cantoneseslang/hongkong-daily-news-note/main/shared/line-qr.png)](https://line.me/R/ti/p/@298mwivr)')
        cleaned_body = re.sub(fr'(?:{cantonese_img1})\n+(?:{cantonese_img1})', r'\g<0>'.replace('\\g<0>','\1'), cleaned_body)
        cleaned_body = re.sub(fr'(?:{cantonese_img2})\n+(?:{cantonese_img2})', r'\g<0>'.replace('\\g<0>','\1'), cleaned_body)

        # 上記のバックリファレンス生成が難しいため明示置換（2回以上の連続を1回へ）
        cleaned_body = re.sub(fr'(?:{cantonese_img1})(?:\n+{cantonese_img1})+', r'[![スラング先生公式LINE](https://raw.githubusercontent.com/cantoneseslang/hongkong-daily-news-note/main/shared/line-img1.jpg)](https://line.me/R/ti/p/@298mwivr)', cleaned_body)
        cleaned_body = re.sub(fr'(?:{cantonese_img2})(?:\n+{cantonese_img2})+', r'[![LINEでお問合せ](https://raw.githubusercontent.com/cantoneseslang/hongkong-daily-news-note/main/shared/line-qr.png)](https://line.me/R/ti/p/@298mwivr)', cleaned_body)
        
        # 連続する空行を1つに
        cleaned_body = re.sub(r'\n{3,}', '\n\n', cleaned_body)
        
        # 先頭・末尾の空行を除去
        cleaned_body = cleaned_body.strip()
        
        return cleaned_body
    
    def remove_duplicate_articles(self, body: str) -> str:
        """生成された記事本文から重複記事を除外"""
        import re
        
        # ### で始まる記事を分割
        articles = re.split(r'\n### ', body)
        
        # 最初の要素は空または天気情報なのでそのまま保持
        if not articles:
            return body
        
        result = [articles[0]]
        seen_title_words: List[Set[str]] = []
        duplicate_count = 0
        
        # 各記事をチェック
        for article in articles[1:]:
            # タイトルを抽出（最初の行）
            lines = article.split('\n', 1)
            if len(lines) > 0:
                title = lines[0].strip()
                
                title_words = normalize_title_words(title)
                # 語数が極端に少ない場合は重複チェックを緩める
                if len(title_words) < 2:
                    result.append(article)
                    continue
                
                if not is_similar_title_words(title_words, seen_title_words):
                    seen_title_words.append(title_words)
                    result.append(article)
                else:
                    duplicate_count += 1
        
        if duplicate_count > 0:
            print(f"🔄 重複記事を除外: {duplicate_count}件")
        
        # 再結合（見出しの前に空行を入れる）
        if len(result) > 1:
            return result[0] + '\n\n### ' + '\n\n### '.join(result[1:])
        else:
            return result[0]
    
    def save_article(self, article: Dict, weather_data: Dict = None, output_path: str = None) -> str:
        """生成した記事をMarkdown形式で保存"""
        if output_path is None:
            timestamp = datetime.now(HKT).strftime('%Y-%m-%d')
            output_path = f"daily-articles/hongkong-news_{timestamp}.md"
        
        # 記事本文から広告コンテンツと重複を除外
        article['body'] = self.remove_advertisement_content(article['body'])
        article['body'] = self.remove_duplicate_articles(article['body'])
        
        # 記事本文から区切り線を削除し、見出し前に空行を追加
        import re
        article['body'] = re.sub(r'\n+---\n+', '\n', article['body'])
        article['body'] = re.sub(r'\n{3,}', '\n\n', article['body'])
        # 見出しの前に必ず空行を入れる
        article['body'] = re.sub(r'([^\n])\n(###)', r'\1\n\n\2', article['body'])
        
        # 天気情報セクションを生成
        weather_section = self.format_weather_info(weather_data) if weather_data is not None else ""
        
        # コンテンツ部分を組み立て（空のセクションは改行を挟まない）
        content_parts = []
        if weather_section:
            content_parts.append(weather_section)
        if article['lead']:
            content_parts.append(article['lead'])
        content_parts.append(article['body'])
        
        # Markdown生成
        content_str = '\n\n'.join(content_parts)
        
        # 広東語学習者向けの定型文を追加
        cantonese_section = self._generate_cantonese_section()
        
        # 見出し画像を生成（記事本文を渡して最初のニュースタイトルを抽出）
        thumbnail_path = self._generate_thumbnail_image(article_body=article['body'])
        
        # front matterにthumbnailを追加
        front_matter = ""
        if thumbnail_path:
            front_matter = f"""---
title: {article['title']}
thumbnail: {thumbnail_path}
---

"""
        
        # bodyの最初に改行を入れる（1行目が空行になり、ここに目次を挿入）
        markdown = f"""{front_matter}# {article['title']}

{content_str}

{cantonese_section}
----
**タグ**: {article['tags']}
**生成日時**: {datetime.now(HKT).strftime('%Y年%m月%d日 %H:%M')}
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        print(f"💾 記事を保存: {output_path}")
        if thumbnail_path:
            print(f"🖼️  見出し画像: {thumbnail_path}")
        return output_path
    
    def _extract_first_news_title(self, article_body: str) -> str:
        """記事本文から最初のニュースタイトル（天気予報の次）を抽出"""
        import re
        
        # 天気セクション全体をスキップ（## 本日の香港の天気から次の##または###まで）
        # 天気セクション内の「### 天気予報」も含めてスキップ
        weather_pattern = r'##\s*本日の香港の天気.*?(?=\n###\s+(?!天気予報)|\n##|$)'
        body_after_weather = re.sub(weather_pattern, '', article_body, flags=re.DOTALL)
        
        # リード文セクションもスキップ（もしあれば）
        # 最初の ### で始まる見出しを探す（「天気予報」以外）
        lines = body_after_weather.split('\n')
        for line in lines:
            line = line.strip()
            # ### で始まり、「天気予報」でない見出しを探す
            if line.startswith('###') and '天気予報' not in line:
                title = line.replace('###', '').strip()
                # 見出しからリンクや余分な文字を除去
                title = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title)  # Markdownリンクを除去
                title = title.strip()
                if title:
                    return title
        
        # フォールバック: 最初の見出しが見つからない場合
        return "香港ニュース"
    
    def _get_outfit_pattern(self) -> str:
        """前日と異なる服装パターンを選択"""
        import random
        import json
        from pathlib import Path
        
        # 10パターンの服装
        outfit_patterns = [
            "wearing a dark brown suit, light brown shirt, and dark navy tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a light orange blouse and brown skirt.",
            "wearing a dark brown suit, pale green shirt, and light brown tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a light sky blue blouse and light brown skirt.",
            "wearing a navy blue suit, blue shirt, and light yellow tie; the woman on the right has shoulder-length brown hair with pony tail, wearing a milly yellow blouse and light gray skirt.",
            "wearing a dark brown suit, light gray shirt, and brown tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a light blue blouse and brown skirt.",
            "wearing a dark blue suit, milky white shirt, and deep blue tie; the woman on the right has shoulder-length brown hair with pony tail, wearing a mily white blouse and light gray skirt.",
            "wearing a milky brown suit, light blue shirt, and light orange tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a light yellow blouse and sky blue skirt.",
            "wearing a dark blue suit, light sky blue shirt, and light yellow tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a light blue blouse and light white skirt.",
            "wearing a dark navy blue suit, blue shirt, and orange tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a pink blouse and light white skirt.",
            "wearing a dark navy blue suit, white shirt, and glay tie; the woman on the right has shoulder-length brown hair with bangs, wearing a white blouse and light glay skirt.",
            "wearing a dark navy blue suit, white shirt, and blue tie; the woman on the right has shoulder-length brown hair with bangs, wearing a white blouse and dark skirt.",
        ]
        
        # 前日の服装パターンを読み込む
        history_file = Path("thumbnail_outfit_history.json")
        last_outfit_index = None
        
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    last_outfit_index = history.get('last_outfit_index')
            except Exception as e:
                print(f"⚠️  服装履歴読み込みエラー: {e}")
        
        # 前日と異なるパターンを選択
        if last_outfit_index is not None:
            available_indices = [i for i in range(len(outfit_patterns)) if i != last_outfit_index]
            selected_index = random.choice(available_indices)
        else:
            selected_index = random.randint(0, len(outfit_patterns) - 1)
        
        # 選択したパターンを保存
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({'last_outfit_index': selected_index}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  服装履歴保存エラー: {e}")
        
        return outfit_patterns[selected_index]
    
    def _generate_thumbnail_image(self, article_body: str = None) -> str:
        """見出し画像を生成して一時保存"""
        try:
            # generate_thumbnail.pyをインポート
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            from generate_thumbnail import generate_thumbnail_for_article
            
            # 日付を取得（例: "2025 11 23"）
            today = datetime.now(HKT)
            # 月と日から先頭の0を除去
            month = str(today.month)
            day = str(today.day)
            date_str = f"{today.year} {month} {day}"
            
            # 最初のニュースタイトルを抽出
            if article_body:
                first_news_title = self._extract_first_news_title(article_body)
            else:
                first_news_title = "香港ニュース"
            
            # 服装パターンを取得
            outfit_pattern = self._get_outfit_pattern()
            
            print(f"🎨 見出し画像生成パラメータ:")
            print(f"   日付: {date_str}")
            print(f"   最初のニュース: {first_news_title[:50]}...")
            print(f"   服装パターン: {outfit_pattern[:50]}...")
            
            # 画像を生成
            thumbnail_path = generate_thumbnail_for_article(
                config_path=self.config_path,
                output_dir="images",
                date_str=date_str,
                first_news_title=first_news_title,
                outfit_pattern=outfit_pattern
            )
            
            return thumbnail_path if thumbnail_path else ""
            
        except Exception as e:
            print(f"⚠️  見出し画像生成エラー: {e}")
            import traceback
            traceback.print_exc()
            return ""

def preprocess_news(news_list):
    """ニュースの事前処理：重複除外、カテゴリー分類、バランス選択"""
    import re
    import os
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    # 0. 過去の記事ファイルから既出ニュースを抽出
    past_urls = set()
    past_title_words: List[Set[str]] = []
    past_title_chars: List[str] = []
    past_event_candidates: List[Dict[str, str]] = []

    recent_selected_news = load_recent_selected_news(days=3)
    if recent_selected_news:
        print(f"🗂️  採用済みrawニュース履歴: {len(recent_selected_news)}件")
        for item in recent_selected_news:
            title = item.get('title', '')
            if title:
                words = normalize_title_words(title)
                if words:
                    past_title_words.append(words)
                chars = normalize_title_chars(title)
                if chars:
                    past_title_chars.append(chars)
                past_event_candidates.append({
                    'title': title,
                    'description': item.get('description', ''),
                })
            url = item.get('url', '')
            normalized = normalize_url(url)
            if normalized:
                past_urls.add(normalized)
    
    for days_ago in range(1, 4):
        past_date = datetime.now(HKT) - timedelta(days=days_ago)
        past_file = f"daily-articles/hongkong-news_{past_date.strftime('%Y-%m-%d')}.md"
        
        if os.path.exists(past_file):
            print(f"📂 過去記事チェック: {past_file}")
            try:
                with open(past_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    url_matches = re.findall(r'\*\*リンク\*\*:\s*(https?://[^\s]+)', content)
                    normalized_urls = {normalize_url(url) for url in url_matches if url}
                    past_urls.update({u for u in normalized_urls if u})
                    
                    title_matches = re.findall(r'^### (.+)$', content, re.MULTILINE)
                    filtered_titles = [t for t in title_matches if '天気' not in t and 'weather' not in t.lower()]
                    for t in filtered_titles:
                        words = normalize_title_words(t)
                        if words:
                            past_title_words.append(words)
                        chars = normalize_title_chars(t)
                        if chars:
                            past_title_chars.append(chars)
                        past_event_candidates.append({
                            'title': t,
                            'description': '',
                        })
                    
                print(f"  ✓ 既出URL: {len(normalized_urls)}件、既出タイトル: {len(filtered_titles)}件")
            except Exception as e:
                print(f"  ⚠️  ファイル読み込みエラー: {e}")
    
    if past_urls or past_title_words:
        print(f"🔍 過去記事から合計 {len(past_urls)} 件のURLと {len(past_title_words)} 件のタイトルを抽出")
    
    # 1. 初期フィルタリング（重複・天気記事・NGワード・トピック過剰・香港無関係記事を除外）
    recent_topics = get_recent_topics(days=3)
    
    # 頻出トピック表示
    if recent_topics:
        print(f"\n📊 過去3日間の頻出トピック:")
        for topic, count in sorted(recent_topics.items(), key=lambda x: -x[1]):
            status = "⚠️ 過剰" if count >= 2 else "✅ 正常"
            print(f"  {status} {topic}: {count}回")
    
    filtered_news = []
    fire_candidates: List[Dict] = []
    fire_limit = 2
    fire_overflow_count = 0
    duplicate_count = 0
    event_duplicate_count = 0
    ng_word_count = 0
    non_hk_count = 0
    overused_topic_count = 0
    
    for news in news_list:
        url = news.get('url', '')
        title = news.get('title', '')
        description = news.get('description', '')
        published_at = news.get('published_at') or news.get('published') or news.get('publishedAt')
        
        normalized_url = normalize_url(url)
        title_words = news.get('_title_words') or normalize_title_words(title)
        news['_title_words'] = title_words
        title_chars = news.get('_title_chars') or normalize_title_chars(title)
        news['_title_chars'] = title_chars
        if '_topic_key' not in news:
            topic_key = derive_topic_key(title)
            if topic_key:
                news['_topic_key'] = topic_key
        news['_normalized_url'] = normalized_url
        news['_source'] = (news.get('source') or 'Unknown').strip() or 'Unknown'
        news['_published_dt'] = parse_published_at(published_at)
        news['_japan_related'] = is_japan_related(title, description, url)
        news['_gba_related'] = is_gba_related(title, description, url)
        
        # 天気記事除外
        weather_keywords = ['気温', '天気', '天文台', '気象', '天候', 'temperature', 'weather', 'observatory', 'forecast', '℃', '度']
        if any(keyword in title.lower() or keyword in title for keyword in weather_keywords):
            duplicate_count += 1
            continue
        
        # NGワード除外（全国運動会など）
        always_ng_keywords = [
            '全国運動会', 'national games', '全運会', '全国運動',
            '宏福苑', '宏福苑火災', '宏福苑火災現場', '香港赤十字会', '大埔宏福苑火災',
        ]
        content_lower = f"{title} {description}".lower()
        if any(keyword.lower() in content_lower for keyword in always_ng_keywords):
            ng_word_count += 1
            continue
        
        if is_fire_related(title, description):
            if len(fire_candidates) < fire_limit:
                fire_candidates.append(news)
            else:
                fire_overflow_count += 1
            continue
        
        # 過剰トピック除外
        if is_overused_topic(title, description, recent_topics, threshold=2):
            overused_topic_count += 1
            continue
        
        # 香港関連度チェック（強化版）
        # 1. 明らかに香港無関係の地域・国をブロック
        non_hk_regions = [
            'ウクライナ', 'ukraine', 'ゼレンスキー', 'zelensky',
            'ロシア', 'russia', 'プーチン', 'putin',
            'オランダ', 'netherlands', 'dutch',
            '大分', '熊本', '福岡', '沖縄', '北海道',  # 日本の地方都市（東京以外）
            'トルコ', 'turkey', 'エルドアン', 'erdogan',
            'イスラエル', 'israel', 'パレスチナ', 'palestine',
        ]
        if any(region in content_lower or region in title.lower() for region in non_hk_regions):
            # ただし、香港キーワードも含まれている場合は許可
            if not any(keyword in content_lower for keyword in ['香港', 'hong kong', 'hongkong']):
                non_hk_count += 1
                continue
        
        # 2. 香港関連キーワードチェック
        hk_keywords = [
            '香港', 'hong kong', 'hk ', ' hk', 'hongkong',
            '立法会', 'legco', '行政長官', '特区政府',
            'mtr', '九龍', 'kowloon', '新界', 'new territories',
            '香港島', 'hong kong island', '中環', 'central',
            '大埔', 'tai po', '屯門', 'tuen mun', '観塘', 'kwun tong',
            '旺角', 'mong kok', '尖沙咀', 'tsim sha tsui',
            '灣仔', 'wan chai', 'wanchai', '銅鑼灣', 'causeway bay',
            'scmp', 'rthk', 'hkfp',  # 香港メディア
            'bn(o)', 'bno',  # 香港人向け制度
        ]
        is_hk_related = any(keyword in content_lower for keyword in hk_keywords)
        if not is_hk_related:
            non_hk_count += 1
            continue
        
        # 重複URL除外
        if normalized_url and normalized_url in past_urls:
            duplicate_count += 1
            continue
        
        # 重複タイトル除外
        title_chars = news.get('_title_chars')
        if title_words and is_similar_title_words(title_words, past_title_words):
            duplicate_count += 1
            continue
        if title_chars and any(
            title_similarity_chars(title_chars, past_chars) >= 0.88
            for past_chars in past_title_chars
        ):
            duplicate_count += 1
            continue

        if any(
            is_same_news_event(title, description, past_item['title'], past_item.get('description', ''))
            for past_item in past_event_candidates
        ):
            event_duplicate_count += 1
            continue
        
        filtered_news.append(news)
    
    if duplicate_count > 0:
        print(f"🚫 過去記事との重複除外: {duplicate_count}件")
    if event_duplicate_count > 0:
        print(f"🚫 過去記事との同一イベント除外: {event_duplicate_count}件")
    if ng_word_count > 0:
        print(f"🚫 NGワード除外（全国運動会等）: {ng_word_count}件")
    if overused_topic_count > 0:
        print(f"🚫 過剰トピック除外: {overused_topic_count}件")
    if non_hk_count > 0:
        print(f"🚫 香港無関係記事除外: {non_hk_count}件")
    
    if fire_candidates:
        filtered_news.extend(fire_candidates)
        print(f"🔥 火災関連ニュースを {len(fire_candidates)}件確保（追加除外 {fire_overflow_count}件）")
    elif fire_overflow_count > 0:
        print(f"🔥 火災関連ニュースは除外されました（候補 {fire_overflow_count}件）")
    
    print(f"📊 フィルタ後: {len(news_list)} → {len(filtered_news)}件")
    
    # 2. 同日内重複除外
    existing_title_words: List[Set[str]] = []
    existing_title_chars: List[str] = []
    existing_event_candidates: List[Dict[str, str]] = []
    unique_news = []
    same_day_duplicates = 0
    same_day_event_duplicates = 0
    
    for news in filtered_news:
        title = news.get('title', '')
        description = news.get('description', '')
        url = news.get('url', '')
        title_words = news.get('_title_words') or normalize_title_words(news.get('title', ''))
        news['_title_words'] = title_words
        title_chars = news.get('_title_chars') or normalize_title_chars(news.get('title', ''))
        news['_title_chars'] = title_chars
        if '_japan_related' not in news:
            news['_japan_related'] = is_japan_related(title, description, url)
        if '_gba_related' not in news:
            news['_gba_related'] = is_gba_related(title, description, url)
        
        if title_words and is_similar_title_words(title_words, existing_title_words):
            same_day_duplicates += 1
            continue
        if title_chars and any(
            title_similarity_chars(title_chars, existing_chars) >= 0.9
            for existing_chars in existing_title_chars
        ):
            same_day_duplicates += 1
            continue

        if any(
            is_same_news_event(title, description, existing_item['title'], existing_item.get('description', ''))
            for existing_item in existing_event_candidates
        ):
            same_day_event_duplicates += 1
            continue
        
        if title_words:
            existing_title_words.append(title_words)
        if title_chars:
            existing_title_chars.append(title_chars)
        existing_event_candidates.append({
            'title': title,
            'description': description,
        })
        unique_news.append(news)
    
    if same_day_duplicates > 0:
        print(f"📊 同日内重複除外: {len(filtered_news)} → {len(unique_news)}件")
    if same_day_event_duplicates > 0:
        print(f"📊 同日内の同一イベント除外: {same_day_event_duplicates}件")
    
    # 3. カテゴリー分類
    categorized = defaultdict(list)
    
    for news in unique_news:
        title_text = news.get('title', '').lower()
        description_text = news.get('description', '').lower()
        content = f"{title_text} {description_text}"
        
        if any(keyword in content for keyword in ['ビジネス', '経済', '金融', '株式', '投資', 'business', 'economy', 'finance', 'stock', 'investment', 'ipo', '上場', '取引所', '銀行', '保険']):
            category = 'ビジネス・経済'
        elif any(keyword in content for keyword in ['テクノロジー', 'ai', '人工知能', 'ロボット', 'デジタル', 'アプリ', 'ソフトウェア', 'ハードウェア', 'technology', 'digital', 'app', 'software', 'hardware', 'スマートフォン', 'コンピューター']):
            category = 'テクノロジー'
        elif any(keyword in content for keyword in ['医療', '健康', '病院', '医師', '薬', '治療', 'medical', 'health', 'hospital', 'doctor', 'medicine', 'treatment', 'covid', 'コロナ', 'ワクチン']):
            category = '医療・健康'
        elif any(keyword in content for keyword in ['教育', '学校', '大学', '学生', '教師', 'education', 'school', 'university', 'student', 'teacher', '学習', '研究']):
            category = '教育'
        elif any(keyword in content for keyword in ['不動産', '住宅', 'マンション', '土地', '賃貸', 'real estate', 'property', 'housing', 'apartment', 'rent', '土地', '建物']):
            category = '不動産'
        elif any(keyword in content for keyword in ['交通', '電車', 'バス', 'タクシー', '空港', 'transport', 'train', 'bus', 'taxi', 'airport', 'mtr', '地下鉄', '路線']):
            category = '交通'
        elif any(keyword in content for keyword in ['犯罪', '逮捕', '警察', '裁判', '刑務所', 'crime', 'arrest', 'police', 'court', 'prison', '違法', '事件', '捜査']):
            category = '治安・犯罪'
        elif any(keyword in content for keyword in ['事故', '災害', '火事', '地震', '台風', 'accident', 'disaster', 'fire', 'earthquake', 'typhoon', '緊急', '救助']):
            category = '事故・災害'
        elif any(keyword in content for keyword in ['政治', '政府', '議員', '選挙', '政策', 'politics', 'government', 'minister', 'election', 'policy', '行政', '議会']):
            category = '政治・行政'
        elif any(keyword in content for keyword in ['スポーツ', 'sports', '試合', '選手', 'メダル', '競技', 'フェンシング', '自転車', 'サッカー', 'バスケ', 'テニス', '水泳', 'match', 'athlete', 'medal', 'game']):
            category = 'スポーツ'
        elif any(keyword in content for keyword in ['文化', '芸能', '映画', '音楽', 'アート', 'culture', 'entertainment', 'movie', 'music', 'art', 'イベント', '祭り', '伝統', 'アーティスト', 'タレント']):
            category = 'カルチャー'
        else:
            category = '社会・その他'
        
        news['category'] = category
        categorized[category].append(news)
    
    print(f"\n📋 カテゴリー別件数:")
    for cat, items in sorted(categorized.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(items)}件")
    
    # 公開日時で各カテゴリをソート
    for cat, items in categorized.items():
        for item in items:
            if '_title_words' not in item:
                item['_title_words'] = normalize_title_words(item.get('title', ''))
            if '_published_dt' not in item:
                published_at = item.get('published_at') or item.get('published') or item.get('publishedAt')
                item['_published_dt'] = parse_published_at(published_at)
            if '_source' not in item:
                item['_source'] = (item.get('source') or 'Unknown').strip() or 'Unknown'
        categorized[cat] = sorted(
            items,
            key=lambda n: (n.get('_published_dt') is not None, n.get('_published_dt')),
            reverse=True
        )
    
    # 4. バランス選択（優先順位に基づいて15-20件選択）
    target_count = 100
    min_desired_articles = 30
    max_per_source_initial = 4
    fallback_category_limit = 10
    category_limits = {
        'ビジネス・経済': 20,
        '社会・その他': 15,
        'カルチャー': 12,
        '政治・行政': 12,
        'テクノロジー': 10,
        '交通': 8,
        '不動産': 8,
        '事故・災害': 5,
        '治安・犯罪': 5,
        '医療・健康': 5,
        '教育': 3,
        'スポーツ': 3,  # 全運会関連は除外済み
    }
    
    priority_cats = [
        'ビジネス・経済',
        '政治・行政',
        '社会・その他',
        'テクノロジー',
        '交通',
        '不動産',
        'カルチャー',
        '事故・災害',
        '治安・犯罪',
        '医療・健康',
        '教育'
    ]
    
    ordered_categories = priority_cats + [
        cat for cat in sorted(categorized.keys())
        if cat not in priority_cats
    ]
    
    priority_requirements = [
        ('_japan_related', 2, '日本関連ニュース'),
        ('_gba_related', 2, '大湾区関連ニュース'),
    ]
    mandatory_news: List[Dict] = []
    mandatory_summary = []
    mandatory_ids = set()
    for flag, minimum, label in priority_requirements:
        group = [n for n in unique_news if n.get(flag)]
        group = sorted(
            group,
            key=lambda n: n.get('_published_dt') or datetime.min,
            reverse=True
        )
        if not group:
            continue
        selected_group = []
        for item in group:
            if id(item) in mandatory_ids:
                continue
            selected_group.append(item)
            mandatory_ids.add(id(item))
            if len(selected_group) >= minimum:
                break
        if selected_group:
            mandatory_news.extend(selected_group)
            mandatory_summary.append((label, len(selected_group)))
    
    if mandatory_summary:
        print("\n⭐ 優先的に確保したトピック:")
        for label, count in mandatory_summary:
            print(f"  {label}: {count}件")
    
    def run_selection(*, topic_cap: Optional[int], limit_source: bool, enforce_category_limit: bool, preselected: Optional[List[Dict]] = None):
        local_selected: List[Dict] = []
        selected_ids = set()
        selected_title_words_local: List[Set[str]] = []
        category_counts = defaultdict(int)
        source_usage = defaultdict(int)
        topic_usage = defaultdict(int)
        topic_exceeded = defaultdict(int)
        
        preselected = preselected or []
        for news in preselected:
            if id(news) in selected_ids:
                continue
            local_selected.append(news)
            selected_ids.add(id(news))
            title_words = news.get('_title_words') or normalize_title_words(news.get('title', ''))
            if title_words:
                selected_title_words_local.append(title_words)
            category = news.get('category', '未分類')
            category_counts[category] += 1
            source = news.get('_source', 'Unknown')
            source_usage[source] += 1
            topic_key = news.get('_topic_key')
            if topic_key:
                topic_usage[topic_key] += 1
        
        for cat in ordered_categories:
            items = categorized.get(cat, [])
            if not items:
                continue
            for news in items:
                if len(local_selected) >= target_count:
                    break
                if id(news) in selected_ids:
                    continue
                
                if enforce_category_limit:
                    limit = category_limits.get(cat, fallback_category_limit)
                    if category_counts[cat] >= limit:
                        continue
                
                source = news.get('_source', 'Unknown')
                if limit_source and source_usage[source] >= max_per_source_initial:
                    continue
                
                title_words = news.get('_title_words') or normalize_title_words(news.get('title', ''))
                if title_words and is_similar_title_words(title_words, selected_title_words_local):
                    continue
                
                topic_key = news.get('_topic_key')
                if topic_cap is not None and topic_key:
                    if topic_usage[topic_key] >= topic_cap:
                        topic_exceeded[topic_key] += 1
                        continue
                
                local_selected.append(news)
                selected_ids.add(id(news))
                if title_words:
                    selected_title_words_local.append(title_words)
                category_counts[cat] += 1
                source_usage[source] += 1
                if topic_key:
                    topic_usage[topic_key] += 1
        return {
            'selected': local_selected,
            'category_counts': category_counts,
            'source_usage': source_usage,
            'topic_usage': topic_usage,
            'topic_exceeded': topic_exceeded,
            'topic_cap': topic_cap,
            'limit_source': limit_source,
            'enforce_category_limit': enforce_category_limit,
        }
    
    selection_strategies = [
        {'topic_cap': 4, 'limit_source': True, 'enforce_category_limit': True},
        {'topic_cap': 8, 'limit_source': False, 'enforce_category_limit': True},
        {'topic_cap': None, 'limit_source': False, 'enforce_category_limit': False},
    ]
    
    selection_result = None
    for attempt, strategy in enumerate(selection_strategies, start=1):
        selection_result = run_selection(**strategy, preselected=mandatory_news)
        selected = selection_result['selected']
        if len(selected) >= min_desired_articles or attempt == len(selection_strategies):
            if len(selected) < min_desired_articles and attempt < len(selection_strategies):
                print(f"⚠️  ニュース件数が {len(selected)} 件と少ないため、抽出条件を緩和します（次の戦略を適用）")
            break
        print(f"⚠️  ニュース件数が {len(selected)} 件と少ないため、抽出条件を緩和します（現在の戦略: topic_cap={strategy['topic_cap']}）")
    
    selected = selection_result['selected']
    topic_exceeded = selection_result['topic_exceeded']
    
    print(f"\n✅ 選択完了: {len(selected)}件（目標: {target_count}件）")
    if selection_result['topic_cap'] is not None:
        print(f"ℹ️  適用トピック上限: {selection_result['topic_cap']}件/トピック")
    else:
        print("ℹ️  トピック上限は適用されていません（最終戦略）")
    
    selected_categories = defaultdict(int)
    for news in selected:
        category = news.get('category', '未分類')
        selected_categories[category] += 1
    
    print("📊 選択されたニュースのカテゴリー別内訳:")
    for cat, count in sorted(selected_categories.items(), key=lambda x: (-x[1], x[0])):
        limit = category_limits.get(cat)
        if limit is not None:
            print(f"  {cat}: {count}件（上限: {limit}件）")
        else:
            print(f"  {cat}: {count}件")
    
    if topic_exceeded:
        print("\n⚠️  トピック上限により除外された件数:")
        for topic, count in sorted(topic_exceeded.items(), key=lambda x: -x[1]):
            print(f"  {topic}: {count}件")
    
    return selected

if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) < 2:
        print("使用方法: python generate_article.py <raw_news.json>")
        sys.exit(1)
    
    # タイムゾーンをHKTに設定（環境変数から取得、なければHKT）
    os.environ['TZ'] = os.environ.get('TZ', 'Asia/Hong_Kong')
    
    news_file = sys.argv[1]
    
    # 今日の日付を表示
    today = datetime.now(HKT).strftime('%Y-%m-%d')
    print(f"\n📅 今日の日付 (HKT): {today}")
    print(f"📅 今日の日付 (日本語): {datetime.now(HKT).strftime('%Y年%m月%d日')}")
    print("=" * 60)
    
    # ニュースデータ読み込み
    with open(news_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n🔍 ニュース事前処理開始")
    print("=" * 60)
    
    # 事前処理：重複除外、カテゴリー分類、バランス選択
    news_data = preprocess_news(data['news'])
    
    print("=" * 60)
    
    # コンフィグパスの決定（優先順位: 環境変数CONFIG_PATH > config.local.json > config.json）
    config_path = os.environ.get('CONFIG_PATH')
    if not config_path:
        if os.path.exists('config.local.json'):
            config_path = 'config.local.json'
        else:
            config_path = 'config.json'

    generator = GrokArticleGenerator(config_path)
    article = generator.generate_article(news_data)
    
    if article:
        # 天気情報も取得（存在する場合）
        weather_data = data.get('weather', None)
        saved_path = generator.save_article(article, weather_data)
        save_selected_news_history(news_data)
        
        # 保存されたファイルの日付を確認
        expected_date = datetime.now(HKT).strftime('%Y-%m-%d')
        file_date = saved_path.split('_')[-1].replace('.md', '')
        
        print(f"\n✅ 記事生成完了！")
        print(f"📁 保存先: {saved_path}")
        print(f"📅 ファイル日付: {file_date}")
        print(f"📅 期待される日付: {expected_date}")
        
        if file_date != expected_date:
            print(f"⚠️  警告: ファイル日付が期待される日付と一致しません！")
            print(f"   ファイル: {file_date}, 期待: {expected_date}")
        
        print(f"\n📝 タイトル: {article['title']}")
        if weather_data:
            print(f"🌤️  天気情報も追加しました")
    else:
        print("\n❌ 記事生成に失敗しました")
        sys.exit(1)
