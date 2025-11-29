#!/usr/bin/env python3
"""
香港ニュース記事生成スクリプト（広東語学習セクション付き）
"""

import json
import os
import requests
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse, urlunparse

try:
    from dateutil import parser as dateutil_parser
except ImportError:  # pragma: no cover - フォールバック用
    dateutil_parser = None

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))


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
            if count >= threshold:  # 過去3日間で2回以上出現
                # トピックキーワードマッチング
                try:
                    if topic == '全国運動会':
                        if re.search(r'全国運動会|national games|全運會|ng\s', content, re.IGNORECASE):
                            return True
                    elif topic == '立法会選挙':
                        if re.search(r'立法会選挙|legco election|立法會選舉|district council', content, re.IGNORECASE):
                            return True
                    elif topic == '施政報告':
                        if re.search(r'施政報告|policy address', content, re.IGNORECASE):
                            return True
                    # その他のトピックは厳しくチェックしない（経済指標等は重要）
                except Exception:
                    pass
        
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
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=300
            )
            
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
                
                return None
                
        except Exception as e:
            print(f"❌ 例外発生: {e}")
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
            title = news.get('title', '')
            description = news.get('description', '')
            url = news.get('url', '')
            source = news.get('source', '')
            published = news.get('published', '')
            
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
        """生成された本文のニュース件数を検証し、足りなければフォールバック生成"""
        expected_count = len(news_data)
        if expected_count == 0:
            return body

        section_count = len(re.findall(r'(?m)^###\s', body))
        if section_count >= expected_count:
            return body

        print(f"⚠️  記事数が不足: 期待 {expected_count} 件に対し {section_count} 件。フォールバック生成を実行します。")

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

            raw_title = (news.get('title') or f"ニュース {idx}").strip()
            translated_title = self._llm_translate_text(raw_title).strip() or raw_title

            summary_source = (news.get('full_content') or news.get('description') or "").strip()
            if len(summary_source) > 1500:
                summary_source = summary_source[:1500]
            translated_summary = self._llm_translate_text(summary_source).strip() if summary_source else ""

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
    duplicate_count = 0
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
        
        # 天気記事除外
        weather_keywords = ['気温', '天気', '天文台', '気象', '天候', 'temperature', 'weather', 'observatory', 'forecast', '℃', '度']
        if any(keyword in title.lower() or keyword in title for keyword in weather_keywords):
            duplicate_count += 1
            continue
        
        # NGワード除外（全国運動会など）
        ng_keywords = [
            '全国運動会', 'national games', '全運会', '全国運動',
            '宏福苑', '宏福苑火災', '宏福苑火災現場', '香港赤十字会', '大埔宏福苑火災',
        ]
        content_lower = f"{title} {description}".lower()
        if any(keyword.lower() in content_lower for keyword in ng_keywords):
            ng_word_count += 1
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
        
        filtered_news.append(news)
    
    if duplicate_count > 0:
        print(f"🚫 過去記事との重複除外: {duplicate_count}件")
    if ng_word_count > 0:
        print(f"🚫 NGワード除外（全国運動会等）: {ng_word_count}件")
    if overused_topic_count > 0:
        print(f"🚫 過剰トピック除外: {overused_topic_count}件")
    if non_hk_count > 0:
        print(f"🚫 香港無関係記事除外: {non_hk_count}件")
    
    print(f"📊 フィルタ後: {len(news_list)} → {len(filtered_news)}件")
    
    # 2. 同日内重複除外
    existing_title_words: List[Set[str]] = []
    existing_title_chars: List[str] = []
    unique_news = []
    same_day_duplicates = 0
    
    for news in filtered_news:
        title_words = news.get('_title_words') or normalize_title_words(news.get('title', ''))
        news['_title_words'] = title_words
        title_chars = news.get('_title_chars') or normalize_title_chars(news.get('title', ''))
        news['_title_chars'] = title_chars
        
        if title_words and is_similar_title_words(title_words, existing_title_words):
            same_day_duplicates += 1
            continue
        if title_chars and any(
            title_similarity_chars(title_chars, existing_chars) >= 0.9
            for existing_chars in existing_title_chars
        ):
            same_day_duplicates += 1
            continue
        
        if title_words:
            existing_title_words.append(title_words)
        if title_chars:
            existing_title_chars.append(title_chars)
        unique_news.append(news)
    
    if same_day_duplicates > 0:
        print(f"📊 同日内重複除外: {len(filtered_news)} → {len(unique_news)}件")
    
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
    selected = []
    selected_ids = set()
    selected_title_words: List[Set[str]] = []
    category_counts = defaultdict(int)
    source_usage = defaultdict(int)
    topic_usage = defaultdict(int)
    topic_exceeded = defaultdict(int)
    
    target_count = 100
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
    
    def select_news(limit_source: bool, enforce_category_limit: bool, categories: List[str]) -> None:
        nonlocal selected
        for cat in categories:
            items = categorized.get(cat, [])
            if not items:
                continue
            for news in items:
                if len(selected) >= target_count:
                    return
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
                if title_words and is_similar_title_words(title_words, selected_title_words):
                    continue
                
                topic_key = news.get('_topic_key')
                if topic_key:
                    topic_limit = 4
                    if topic_usage[topic_key] >= topic_limit:
                        topic_exceeded[topic_key] += 1
                        continue
                
                selected.append(news)
                selected_ids.add(id(news))
                if title_words:
                    selected_title_words.append(title_words)
                category_counts[cat] += 1
                source_usage[source] += 1
                if topic_key:
                    topic_usage[topic_key] += 1
                if len(selected) >= target_count:
                    return
    
    # 1st pass: respect category limits and per-source cap
    select_news(limit_source=True, enforce_category_limit=True, categories=ordered_categories)
    
    # 2nd pass: relax source cap but keep category limits
    if len(selected) < target_count:
        select_news(limit_source=False, enforce_category_limit=True, categories=ordered_categories)
    
    # Final pass: fill remaining slots without category limits
    if len(selected) < target_count:
        select_news(limit_source=False, enforce_category_limit=False, categories=ordered_categories)
    
    print(f"\n✅ 選択完了: {len(selected)}件（目標: {target_count}件）")
    
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
