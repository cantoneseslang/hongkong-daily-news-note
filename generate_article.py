#!/usr/bin/env python3
"""
Grok APIを使用して香港ニュースから日本語記事を生成
※ 要約や短縮は一切行わず、元の情報をそのまま翻訳する
"""

import requests
import json
from datetime import datetime
from typing import List, Dict

class GrokArticleGenerator:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.api_key = self.config['grok_api']['api_key']
        self.api_url = self.config['grok_api']['api_url']
        
    def generate_article(self, news_data: List[Dict]) -> Dict:
        """Grok APIで日本語記事を生成"""
        print("\n🤖 Grok APIで記事生成中...")
        print("=" * 60)
        
        # ニュースデータを整形
        news_text = self._format_news_for_prompt(news_data)
        
        # 香港時間（HKT）で現在の日付を取得
        from datetime import datetime, timezone, timedelta
        hkt = timezone(timedelta(hours=8))  # UTC+8
        current_hkt_date = datetime.now(hkt)
        
        # Grok APIへのプロンプト
        system_prompt = """あなたは香港のニュースを日本語に翻訳し、指定されたフォーマットで整形する翻訳者です。

【最重要】要約や短縮は絶対禁止。元のニュース内容(Full Content)をそのまま全文日本語に翻訳してください。

【記事構成】
各ニュースは以下のMarkdown形式で記載（番号なし）:

### [ニュースタイトル]

[Full Contentを全文翻訳、段落は空白行で区切る]

**引用元**: [source名], [日付]  
**リンク**: [完全なURL]  
**備考**: [重要性や日本との関連性を1文で]

---

### [次のニュースタイトル]

[Full Contentを全文翻訳]

**引用元**: [source名], [日付]  
**リンク**: [完全なURL]  
**備考**: [重要性や日本との関連性を1文で]

【出力例】
### 香港立法会、ライドシェア規制法案可決

香港の立法会は、ライドシェアサービスを規制する法案を可決しました。

運輸局の陳美宝局長は、この法案が交通サービスを近代化すると述べました。

ライドシェア事業者はライセンス取得が必要になります。

**引用元**: SCMP, 2025年10月16日  
**リンク**: https://www.scmp.com/...  
**備考**: 交通政策の転機で即時性が高い。

---

### 台湾で香港人観光客が強姦される事件後、公衆安全の改善を求めるアドボカシーグループ

香港の観光客が昼間、台北駅で知人であり逃亡中の男によって強姦されたとされる事件後、アドボカシーグループは公衆安全と傍観者の介入の改善を求めています。

**引用元**: SCMP, 2025年10月16日  
**リンク**: https://www.scmp.com/...  
**備考**: 香港人観光客の安全に関わる事件として注目される。

【重要】
- 番号（1. 2. など）は絶対に使用しない
- 各ニュースのタイトルは「### タイトル名」形式で小見出しにする
- ニュース間は「---」で区切る
- 引用元、リンク、備考は「**項目名**:」形式で太字にする
- Google Newsのリダイレクトリンク（news.google.com/rss/articles/...）は使用しない。元のソース（HK01、Yahoo等）の実リンクを使用すること

【翻訳ルール】
- 地名: 天水圍(ティン・シュイ・ワイ)、調景嶺(ティウ・ケン・レン)のように漢字+読み仮名
- 人名: 李英華(Li Ying-wah)のように漢字+英語読み
- 組織名: 廉政公署(ICAC)のように漢字+略称
- 数字・金額: そのまま翻訳
- 固有名詞: 原語を尊重

【絶対に守ること】
- Full Contentの短縮・要約は絶対禁止
- 元の情報をすべて含める
- 文字数制限なし
- 香港関連のニュースのみ選択（最大20件）
- 重要度の高い順に並べる
- 広告記事（presented, sponsored含むURL）は除外

【出力形式】
必ず以下のJSON形式で返してください。JSON以外の文字は一切含めないでください：
{{
  "title": "毎日AIピックアップニュース({current_hkt_date.strftime('%Y年%m月%d日')})",
  "lead": "",
  "body": "上記フォーマットのMarkdown記事",
  "tags": "香港,ニュース,最新,情報,アジア"
}}

【重要】JSON形式のみで回答し、他の説明文や追加テキストは一切含めないでください。"""

        user_prompt = f"""以下は{current_hkt_date.strftime('%Y年%m月%d日')}の香港ニュースです。
これらの情報を元に、指定されたフォーマットで日本語記事を作成してください。

【最重要】Full Contentの内容は絶対に短縮・要約せず、全文そのまま日本語に翻訳してください。
- 1つの記事の内容は最低500文字以上にする
- 元の情報をすべて含める
- 具体的な固有名詞、数字、日付をすべて含める

{news_text}

上記のニュースから香港関連のものを20件選び、指定されたフォーマットでJSON形式で出力してください。20件のニュース記事を必ず作成してください。
各ニュースの「内容」は元のFull Contentを全文翻訳してください（短縮禁止）。

【最重要ルール：重複の排除】
1. **同じ事件・イベントについて、複数のソース（SCMP、RTHK、Yahoo等）から報道されている場合、最も詳細な1つだけを選択してください**
2. **例：「華懋タワー火災」など、同じ火災事件は1つだけ**
3. 各記事は異なるトピック・事件である必要があります

【重要】利用可能なニュースから**異なる事件・トピック**を必ず20件選び、記事を生成してください。20件を目標に、できるだけ多くの記事を生成してください。"""

        # APIリクエスト
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "model": "grok-2-latest",
            "stream": False,
            "temperature": 0.1  # 正確性を最優先
        }
        
        try:
            print("📤 Grok APIにリクエスト送信中...")
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=300  # 120秒 → 300秒（5分）に延長
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print("✅ 記事生成完了")
                
                # JSONパース
                try:
                    import re
                    
                    # コードブロックを除去
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0].strip()
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0].strip()
                    
                    # JSONとして最初の { から最後の } を抽出
                    if '{' in content and '}' in content:
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        json_str = content[start:end]
                        
                        # 制御文字を完全に除去
                        json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\t')
                        
                        article = json.loads(json_str)
                        return article
                    else:
                        raise json.JSONDecodeError("No JSON object found", content, 0)
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSONパースエラー: {e}")
                    print(f"   レスポンス内容: {content[:500]}...")
                    print("   テキストから記事を抽出中...")
                    
                    # JSON形式を諦めて、テキストから抽出
                    lines = content.split('\n')
                    title_line = [l for l in lines if 'title' in l.lower() and ':' in l]
                    if title_line:
                        title = title_line[0].split(':', 1)[1].strip().strip('"').strip(',').strip('"')
                    else:
                        title = f"毎日AIピックアップニュース({current_hkt_date.strftime('%Y年%m月%d日')})"
                    
                    # テキストから記事を抽出
                    lines = content.split('\n')
                    title_line = [l for l in lines if 'title' in l.lower() and ':' in l]
                    if title_line:
                        title = title_line[0].split(':', 1)[1].strip().strip('"').strip(',').strip('"')
                    else:
                        title = f"毎日AIピックアップニュース({current_hkt_date.strftime('%Y年%m月%d日')})"
                    
                    # bodyからMarkdown記事を抽出
                    body_start = content.find('"body":')
                    if body_start != -1:
                        body_start = content.find('"', body_start + 7) + 1
                        body_end = content.rfind('"')
                        if body_end > body_start:
                            body = content[body_start:body_end]
                            # JSONエスケープを解除
                            body = body.replace('\\n', '\n').replace('\\"', '"').replace('\\/', '/')
                        else:
                            body = content
                    else:
                        body = content
                    
                    return {
                        "title": title,
                        "lead": "",
                        "body": body,
                        "tags": "香港,ニュース,最新,情報,アジア"
                    }
            else:
                print(f"❌ APIエラー: {response.status_code}")
                print(f"   詳細: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 例外発生: {e}")
            return None
    
    def _format_news_for_prompt(self, news_data: List[Dict]) -> str:
        """ニュースデータをプロンプト用に整形"""
        formatted = []
        for i, news in enumerate(news_data, 1):  # 全件使用
            # full_contentがあればそれを使用、なければdescription
            content = news.get('full_content', news.get('description', 'N/A'))
            formatted.append(f"""
【ニュース{i}】
Title: {news.get('title', 'N/A')}
Full Content: {content}
Source: {news.get('source', 'N/A')}
URL: {news.get('url', 'N/A')}
Published: {news.get('published_at', 'N/A')}
""")
        return "\n".join(formatted)
    
    def format_weather_info(self, weather_data: Dict) -> str:
        """天気情報をMarkdown形式に整形"""
        if not weather_data:
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
                if line:  # 空行は除外
                    cleaned_lines.append(line)
            # 適切な改行で結合
            return ' '.join(cleaned_lines)
        
        weather_section = "## 本日の香港の天気"
        
        # 天気警報
        if 'weather_warning' in weather_data:
            warning = weather_data['weather_warning']
            title = warning.get('title', 'N/A')
            desc = clean_weather_text(warning.get('description', ''))
            
            # 天気警報を完全にフィルター（現時並無警告生效、酷熱天氣警告など）
            if title and "現時並無警告生效" not in title and "酷熱天氣警告" not in title and "發出" not in title:
                weather_section += f"\n### 天気警報{title}"
                if desc and "現時並無警告生效" not in desc and "酷熱天氣警告" not in desc:
                    weather_section += f"{desc}"
        
        # 地域天気予報のみ表示
        if 'weather_forecast' in weather_data:
            forecast = weather_data['weather_forecast']
            title = forecast.get('title', 'N/A')
            desc = clean_weather_text(forecast.get('description', ''))
            
            # タイトルを日本語に翻訳
            translated_title = self._translate_weather_text(title)
            
            # 本文を日本語に翻訳
            if desc and len(desc) < 1000:  # 長すぎる場合はスキップ
                translated_desc = self._translate_weather_text(desc)
                
                # 改行なしで一行にまとめる
                weather_section += f"\n### 天気予報\n{translated_title} {translated_desc}\n\n**引用元**: 香港天文台"
            else:
                weather_section += f"\n### 天気予報\n{translated_title}\n\n**引用元**: 香港天文台"
        
        return weather_section
    
    def _translate_weather_text(self, text: str) -> str:
        """天気情報のテキストを中国語・広東語から日本語に翻訳"""
        if not text or len(text.strip()) == 0:
            return text
        
        try:
            import requests
            import json
            
            # Google Translate APIを使用して翻訳
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': 'zh',  # 中国語から
                'tl': 'ja',  # 日本語へ
                'dt': 't',
                'q': text
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0 and len(result[0]) > 0:
                    translated = ''.join([item[0] for item in result[0] if item[0]])
                    return translated.strip()
            
            return text  # 翻訳に失敗した場合は元のテキストを返す
            
        except Exception as e:
            print(f"⚠️  天気翻訳エラー: {e}")
            return text  # エラーの場合は元のテキストを返す
    
    def remove_duplicate_articles(self, body: str) -> str:
        """生成された記事本文から重複記事を除外"""
        import re
        
        # ### で始まる記事を分割
        articles = re.split(r'\n### ', body)
        
        # 最初の要素は空または天気情報なのでそのまま保持
        if articles:
            result = [articles[0]]
            seen_titles = set()
            duplicate_count = 0
            
            for article in articles[1:]:
                # タイトルを抽出（最初の行）
                lines = article.split('\n', 1)
                if len(lines) > 0:
                    title = lines[0].strip()
                    
                    # タイトルの正規化（小文字化、記号除去）
                    normalized_title = re.sub(r'[^\w\s]', '', title.lower())
                    
                    # 重複チェック
                    if normalized_title not in seen_titles and normalized_title:
                        seen_titles.add(normalized_title)
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
        
        return body
    
    def save_article(self, article: Dict, weather_data: Dict = None, output_path: str = None) -> str:
        """生成した記事をMarkdown形式で保存"""
        if output_path is None:
            # 香港時間（HKT）で現在の日付を取得
            from datetime import datetime, timezone, timedelta
            hkt = timezone(timedelta(hours=8))  # UTC+8
            current_hkt_date = datetime.now(hkt)
            timestamp = current_hkt_date.strftime('%Y-%m-%d')
            output_path = f"daily-articles/hongkong-news_{timestamp}.md"
        
        # 記事本文から重複を除外
        article['body'] = self.remove_duplicate_articles(article['body'])
        
        # 記事本文から区切り線を削除し、見出し前に空行を追加
        import re
        article['body'] = re.sub(r'\n+---\n+', '\n', article['body'])
        article['body'] = re.sub(r'\n{3,}', '\n\n', article['body'])
        # 見出しの前に必ず空行を入れる
        article['body'] = re.sub(r'([^\n])\n(###)', r'\1\n\n\2', article['body'])
        
        # 天気情報セクションを生成
        weather_section = self.format_weather_info(weather_data) if weather_data else ""
        
        # コンテンツ部分を組み立て（空のセクションは改行を挟まない）
        content_parts = []
        if weather_section:
            content_parts.append(weather_section)
        if article['lead']:
            content_parts.append(article['lead'])
        content_parts.append(article['body'])
        
        # 香港時間（HKT）で現在の日付を取得
        from datetime import datetime, timezone, timedelta
        hkt = timezone(timedelta(hours=8))  # UTC+8
        current_hkt_date = datetime.now(hkt)
        
        # Markdown生成
        content_str = '\n\n'.join(content_parts)
        # bodyの最初に改行を入れる（1行目が空行になり、ここに目次を挿入）
        markdown = f"""# {article['title']}

{content_str}
---
**タグ**: {article['tags']}
**生成日時**: {current_hkt_date.strftime('%Y年%m月%d日 %H:%M')}
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        print(f"💾 記事を保存: {output_path}")
        return output_path

def preprocess_news(news_list):
    """ニュースの事前処理：重複除外、カテゴリー分類、バランス選択"""
    import re
    import os
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    # 0. 過去の記事ファイルから既出ニュースを抽出
    past_urls = set()
    past_titles = []
    
    # 過去3日分の記事ファイルをチェック
    for days_ago in range(1, 4):
        past_date = datetime.now() - timedelta(days=days_ago)
        past_file = f"daily-articles/hongkong-news_{past_date.strftime('%Y-%m-%d')}.md"
        
        if os.path.exists(past_file):
            print(f"📂 過去記事チェック: {past_file}")
            try:
                with open(past_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # URLを抽出（**リンク**: の後のURL）
                    url_matches = re.findall(r'\*\*リンク\*\*:\s*(https?://[^\s]+)', content)
                    past_urls.update(url_matches)
                    
                    # タイトルを抽出（### の後のタイトル）
                    title_matches = re.findall(r'^### (.+)$', content, re.MULTILINE)
                    # 天気予報のタイトルは除外
                    past_titles.extend([t for t in title_matches if '天気' not in t and 'weather' not in t.lower()])
                    
                print(f"  ✓ 既出URL: {len(url_matches)}件、既出タイトル: {len([t for t in title_matches if '天気' not in t])}件")
            except Exception as e:
                print(f"  ⚠️  ファイル読み込みエラー: {e}")
    
    if past_urls:
        print(f"🔍 過去記事から合計 {len(past_urls)} 件のURLと {len(past_titles)} 件のタイトルを抽出")
    
    # 過去記事との重複を除外
    filtered_news = []
    duplicate_count = 0
    
    for news in news_list:
        url = news.get('url', '')
        title = news.get('title', '')
        description = news.get('description', '')
        
        # 天気関連のニュースを除外
        weather_keywords = ['気温', '天気', '天文台', '気象', '天候', 'temperature', 'weather', 'observatory', 'forecast', '℃', '度']
        if any(keyword in title.lower() or keyword in title for keyword in weather_keywords):
            duplicate_count += 1
            continue
        
        # URLで重複チェック
        if url in past_urls:
            duplicate_count += 1
            continue
        
        # タイトルの類似性チェック
        is_similar = False
        for past_title in past_titles:
            # タイトルを正規化して比較
            def normalize_title(t):
                t = t.lower()
                t = re.sub(r'[^\w\s]', '', t)
                return set(t.split())
            
            title_words = normalize_title(title)
            past_title_words = normalize_title(past_title)
            
            # 共通単語をチェック
            common_words = title_words & past_title_words
            
            # 3単語以上共通 かつ 共通率が70%以上なら重複とみなす
            if len(common_words) >= 3:
                similarity = len(common_words) / max(len(title_words), len(past_title_words), 1)
                if similarity >= 0.7:
                    is_similar = True
                    break
        
        if is_similar:
            duplicate_count += 1
            continue
        
        filtered_news.append(news)
    
    if duplicate_count > 0:
        print(f"🚫 過去記事との重複除外: {duplicate_count}件")
    
    print(f"📊 フィルタ後: {len(news_list)} → {len(filtered_news)}件")
    
    # 1. タイトルの類似度による重複除外（強化版）
    unique_news = []
    seen_titles = []
    
    for news in filtered_news:
        title = news['title']
        
        # タイトルを単語に分割して正規化
        def extract_keywords(text):
            # 記号を除去して単語を抽出
            words = re.sub(r'[^\w\s]', ' ', text).split()
            # 2文字以上の単語のみ（ストップワードを除く）
            stop_words = {'の', 'に', 'を', 'は', 'が', 'と', 'で', 'や', 'も', 'から', 'まで', 'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
            keywords = [w.lower() for w in words if len(w) >= 2 and w.lower() not in stop_words]
            return set(keywords)
        
        current_keywords = extract_keywords(title)
        
        # 既存のタイトルと比較
        is_duplicate = False
        for seen_title in seen_titles:
            seen_keywords = extract_keywords(seen_title)
            
            # 共通キーワードの割合を計算
            if len(current_keywords) > 0 and len(seen_keywords) > 0:
                common = current_keywords & seen_keywords
                
                # 主要キーワード（3文字以上）を重視
                current_major = {k for k in current_keywords if len(k) >= 3}
                seen_major = {k for k in seen_keywords if len(k) >= 3}
                common_major = current_major & seen_major
                
                # 主要キーワードが2つ以上一致、かつ全体の類似度が70%以上なら重複
                if len(common_major) >= 2:
                    similarity = len(common) / min(len(current_keywords), len(seen_keywords))
                    if similarity >= 0.7:
                        is_duplicate = True
                        break
        
        if not is_duplicate:
            seen_titles.append(title)
            unique_news.append(news)
    
    print(f"📊 同日内重複除外: {len(filtered_news)} → {len(unique_news)}件")
    
    # 2. カテゴリー分類
    categorized = defaultdict(list)
    
    for news in unique_news:
        title = news['title'].lower()
        desc = news.get('description', '').lower()
        text = title + ' ' + desc
        
        # カテゴリー判定
        if any(k in text for k in ['business', 'economy', 'finance', 'market', 'stock', 'trade', 'yuan', 'dollar', '經濟', '財經', '股', '貿易']):
            cat = 'ビジネス・経済'
        elif any(k in text for k in ['property', 'housing', 'home', 'flat', 'homebuyer', '樓', '房屋', '物業']):
            cat = '不動産'
        elif any(k in text for k in ['tech', 'technology', 'ai', 'digital', 'robot', '科技', '機械人']):
            cat = 'テクノロジー'
        elif any(k in text for k in ['health', 'medical', 'hospital', 'doctor', '醫療', '健康', '醫院']):
            cat = '医療・健康'
        elif any(k in text for k in ['education', 'university', 'school', 'student', 'hostel', '教育', '大學', '學生']):
            cat = '教育'
        elif any(k in text for k in ['art', 'culture', 'entertainment', 'exhibition', 'drama', '文化', '藝術', '展覽', '演出']):
            cat = 'カルチャー'
        elif any(k in text for k in ['weather', 'storm', 'typhoon', '天氣', '風暴', '颱風']):
            cat = '天気'
        elif any(k in text for k in ['traffic', 'transport', 'car', 'road', '交通', '道路', '車']):
            cat = '交通'
        elif any(k in text for k in ['police', 'arrest', 'crime', 'vice', '警', '拘捕', '罪案']):
            cat = '治安・犯罪'
        elif any(k in text for k in ['fire', 'dead', 'accident', '火災', '死亡', '意外']):
            cat = '事故・災害'
        elif any(k in text for k in ['government', 'policy', 'election', 'official', '政府', '政策', '選舉', '官員']):
            cat = '政治・行政'
        else:
            cat = '社会・その他'
        
        categorized[cat].append(news)
    
    print(f"\n📋 カテゴリー別件数:")
    for cat, items in sorted(categorized.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(items)}件")
    
    # 3. バランス選択（各カテゴリーから均等に選ぶ）
    selected = []
    target_count = 30  # 30件に絞る（APIタイムアウト防止）
    
    # カテゴリーごとの優先順位
    priority_cats = [
        'ビジネス・経済', '不動産', 'テクノロジー', '医療・健康', 
        '教育', 'カルチャー', '交通', '治安・犯罪', '事故・災害',
        '政治・行政', '天気', '社会・その他'
    ]
    
    # 各カテゴリーから選択
    while len(selected) < target_count:
        added = False
        for cat in priority_cats:
            if cat in categorized and categorized[cat]:
                selected.append(categorized[cat].pop(0))
                added = True
                if len(selected) >= target_count:
                    break
        if not added:
            break
    
    print(f"\n✅ 選択完了: {len(selected)}件（バランス調整済み）")
    
    return selected

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python generate_article.py <raw_news.json>")
        sys.exit(1)
    
    news_file = sys.argv[1]
    
    # ニュースデータ読み込み
    with open(news_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n🔍 ニュース事前処理開始")
    print("=" * 60)
    
    # 事前処理：重複除外、カテゴリー分類、バランス選択
    news_data = preprocess_news(data['news'])
    
    print("=" * 60)
    
    generator = GrokArticleGenerator()
    article = generator.generate_article(news_data)
    
    if article:
        # 天気情報も取得（存在する場合）
        weather_data = data.get('weather', None)
        saved_path = generator.save_article(article, weather_data)
        print(f"\n✅ 記事生成完了！")
        print(f"📁 保存先: {saved_path}")
        print(f"\n📝 タイトル: {article['title']}")
        if weather_data:
            print(f"🌤️  天気情報も追加しました")
    else:
        print("\n❌ 記事生成に失敗しました")
