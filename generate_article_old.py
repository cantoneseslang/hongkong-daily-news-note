#!/usr/bin/env python3
"""
Grok APIを使用して香港ニュースから日本語記事を生成
※ 要約や短縮は一切行わず、元の情報をそのまま翻訳する
"""

import requests
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class GrokArticleGenerator:
    def __init__(self, config_path: str = "config.json"):
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
        
        # GPT-4 APIへのプロンプト
        system_prompt = """ニュースを日本語に翻訳してJSON形式で返してください。

翻訳ルール：
- すべてのテキストを日本語に翻訳
- 要約しない

出力形式：
{
  "title": "毎日AIピックアップニュース(2025年10月28日)",
  "lead": "",
  "body": "### タイトル\\n\\n本文\\n\\n**引用元**: ソース, 日付\\n**リンク**: URL\\n**備考**: 説明\\n\\n---\\n\\n### 次のニュース...",
  "tags": "香港,広東語,廣東話,中国語ニュース,最新,情報,アジア"
}"""

        user_prompt = f"""以下は{datetime.now(HKT).strftime('%Y年%m月%d日')}の香港ニュースです。
これらの情報を元に、指定されたフォーマットで日本語記事を作成してください。

【最重要】Full Contentの内容は絶対に短縮・要約せず、全文そのまま日本語に翻訳してください。

【翻訳徹底指示】
- 中国語・広東語の固有名詞や地名は必ず適切な日本語に翻訳する
- 感染症名は正確な日本語医学用語を使用：
  * 「基孔肯雅熱」→「チクングニア熱」（注：これらのニュースは除外される）
  * 「登革熱」→「デング熱」
- 地名は標準的なカタカナ表記：
  * 「鳳徳邨」→「フェンタク村」（広東語読み）
  * 「衛生防護センター」→「衛生防護センター」（職能名）
- 専門用語は正確な日本語表記を使用し、医学・公衆衛生用語は特に注意
- 引用や会話部分の中国語もすべて日本語に翻訳する
- 【】内の中国語もすべて翻訳する
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

【重要】利用可能なニュースから**異なる事件・トピック**を必ず20件選び、記事を生成してください。20件を目標に、できるだけ多くの記事を生成してください。

【除外すべき政治関連ニュース】
以下のテーマを含むニュースは絶対に選ばないでください：
- 47人事件、47 persons case、democracy trial
- 刑期満了、prison release、sentence completion
- 民主派、democratic party、pro-democracy
- 立法会選挙、legislative council election、legco election
- 国家安全公署、national security office、国安法
- jailed for conspiracy (政治的事件での逮捕・判決)
- 2019 protest related news

【優先的に選ぶべきニュース】
政治ニュースの代わりに、以下のカテゴリーのニュースを優先的に選んでください：
- **芸能・カルチャー（最優先）**: 俳優、歌手、テレビ番組、番組終了、TVB、生日、婚紗、停播など
- ビジネス・経済: 企業ニュース、IPO、市場動向
- テクノロジー: AI、デジタルイノベーション
- 健康・医療: 感染症、医療技術
- スポーツ
- 不動産
- 教育
- 社会イベント

**重要な選択ガイドライン**:
1. 提供されたニュースリストから、**芸能・カルチャーニュースを最低3-5件は必ず選んでください**
2. 俳優名、番組名、TVB関連のニュースは積極的に選択してください
3. 政治関連のニュースは完全に無視してください
4. ビジネス、健康、テクノロジーのニュースも多く選んでください

これらの政治関連のニュースは一切取り扱わず、特に芸能・カルチャーニュースを最優先に、ビジネス、テクノロジー、健康、文化、スポーツ、不動産、教育などのニュースを選択してください。"""

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
                    "maxOutputTokens": 32000
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
                    "max_tokens": 32000
                }
            else:  # Grok API
                payload = {
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 32000
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
                
                # JSONパース
                try:
                    # コードブロックを除去
                    if content.strip().startswith('```'):
                        lines = content.split('\n')
                        # 最初の```行をスキップ、最後の```行もスキップ
                        start_line = 1 if len(lines) > 1 else 0
                        end_line = len(lines) - 1 if len(lines) > 1 and lines[-1].strip() == '```' else len(lines)
                        content = '\n'.join(lines[start_line:end_line]).strip()
                    
                    # JSONとして最初の { から最後の } を抽出
                    if '{' in content and '}' in content:
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        json_str = content[start:end]
                        
                        # 制御文字を除去
                        json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\t\r')
                        
                        article = json.loads(json_str)
                        return article
                    
                    raise json.JSONDecodeError("No JSON object found", content, 0)
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSONパースエラー: {e}")
                    print(f"   レスポンス内容: {content[:500]}...")
                    print("   テキストから記事を抽出中...")
                    
                    # JSON形式を諦めて、テキストから抽出
                    # 最初にコードブロックを除去した content を使用
                    lines = content.split('\n')
                    title_line = [l for l in lines if 'title' in l.lower() and ':' in l]
                    if title_line:
                        title = title_line[0].split(':', 1)[1].strip().strip('"').strip(',').strip('"')
                    else:
                        title = f"毎日AIピックアップニュース({datetime.now(HKT).strftime('%Y年%m月%d日')})"
                    
                    # bodyからMarkdown記事を抽出（改良版）
                    body_start = content.find('"body":')
                    if body_start != -1:
                        # "body": の後の最初の " を探す
                        quote_start = content.find('"', body_start + 7)
                        if quote_start != -1:
                            # 次の " を探す（エスケープされた " は考慮）
                            body_end = quote_start + 1
                            while body_end < len(content):
                                if content[body_end] == '"' and content[body_end - 1] != '\\':
                                    break
                                body_end += 1
                            
                            if body_end > quote_start + 1:
                                body = content[quote_start + 1:body_end]
                                # JSONエスケープを解除
                                body = body.replace('\\n', '\n').replace('\\"', '"').replace('\\/', '/')
                            else:
                                body = ""
                        else:
                            body = ""
                    else:
                        body = ""
                    
                    return {
                        "title": title,
                        "lead": "",
                        "body": body,
                        "tags": "香港,広東語,廣東話,中国語ニュース,最新,情報,アジア"
                    }
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
            
            # 天気情報を日本語に翻訳
            translated_title = self._translate_weather_text(title)
            translated_desc = self._translate_weather_text(desc)
            weather_section += f"\n### 天気予報\n{translated_title}\n{translated_desc}\n\n**引用元**: 香港天文台"
        
        return weather_section
    
    def _translate_weather_text(self, text: str) -> str:
        """天気情報の広東語を日本語に翻訳"""
        if not text:
            return ""
        
        # 広東語の天気情報を日本語に翻訳する辞書
        weather_translations = {
            "香港天文台於": "香港天文台が",
            "發出之天氣報告": "発表した天気報告",
            "一股清勁的偏東氣流正影響廣東沿岸": "清涼な東風が広東沿岸に影響しています",
            "此外": "また",
            "一道雲帶正覆蓋華南沿岸": "雲が華南沿岸を覆っています",
            "本港地區今日天氣預測": "香港地区の今日の天気予報",
            "大致多雲": "概ね曇り",
            "有一兩陣微雨": "時々小雨",
            "日間短暫時間有陽光": "日中は短時間晴れ間",
            "吹和緩至清勁東至東北風": "東から北東の風がやや強く吹く",
            "展望": "今後の見通し",
            "明日日間炎熱": "明日の日中は暑い",
            "週末期間氣溫稍為下降": "週末は気温がやや下がり",
            "天氣乾燥": "天気は乾燥",
            "下週初風勢頗大": "来週初めは風が強い"
        }
        
        # 翻訳を適用
        translated_text = text
        for chinese, japanese in weather_translations.items():
            translated_text = translated_text.replace(chinese, japanese)
        
        return translated_text
    
    def _generate_cantonese_section(self) -> str:
        """広東語学習者向けの定型文を生成"""
        return """## 広東語学習者向け情報

広東語学習者向けにLINEが良い、便利という方もいるでしょうから、スラング先生公式アカウントもありますのでこちらご登録してから使用してください。秘書のリーさんが広東語についてなんでも回答してくれますのでぜひ使ってみてください

(今現在400名以上の方に登録していただいております）

[スラング先生LINE公式アカウント](https://line.me/R/ti/p/@298mwivr)

[![スラング先生公式LINE](../shared/line-img1.jpg)](https://line.me/R/ti/p/@298mwivr)

[![LINEでお問合せ](../shared/line-qr.png)](https://line.me/R/ti/p/@298mwivr)

## 広東語| 広東語超基礎　超簡単！初めての広東語「9声6調」

@https://youtu.be/RAWZAJUrvOU?si=WafOkQixyLiwMhUW"""
    
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
            r'新規会員登録.*?プレゼント'
        ]
        
        # 広告コンテンツを除去
        cleaned_body = body
        for pattern in ad_patterns:
            cleaned_body = re.sub(pattern, '', cleaned_body, flags=re.DOTALL | re.IGNORECASE)
        
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
        if articles:
            result = [articles[0]]
            seen_titles = set()
            duplicate_count = 0
            
            for article in articles[1:]:
                # タイトルを抽出（最初の行）
                lines = article.split('\n', 1)
                if len(lines) > 0:
                    title = lines[0].strip()
                    
                    # タイトルの正規化（より厳密な重複のみ除外）
                    normalized_title = re.sub(r'[^\w\s]', '', title.lower())
                    # 短すぎるタイトルは重複チェック対象外
                    if len(normalized_title) < 10:
                        result.append(article)
                        continue
                    
                    # 重複チェック（完全一致のみ）
                    if normalized_title not in seen_titles:
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
        weather_section = self.format_weather_info(weather_data) if weather_data else ""
        
        # コンテンツ部分を組み立て（空のセクションは改行を挟まない）
        content_parts = []
        if weather_section:
            content_parts.append(weather_section)
        if article['lead']:
            content_parts.append(article['lead'])
        content_parts.append(article['body'])
        
        # Markdown生成
        content_str = '\n\n'.join(content_parts)
        # bodyの最初に改行を入れる（1行目が空行になり、ここに目次を挿入）
        markdown = f"""# {article['title']}

{content_str}
---
**タグ**: {article['tags']}
**生成日時**: {datetime.now(HKT).strftime('%Y年%m月%d日 %H:%M')}
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
        past_date = datetime.now(HKT) - timedelta(days=days_ago)
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
        
        # 政治関連のニュースを除外
        political_keywords = [
            '47人', '47 persons', '47 activists', 'democracy trial',
            '刑期満了', 'prison term', 'sentence completion', 'prison release',
            '民主派', 'democratic', 'democrats', 'pro-democracy',
            '立法会選挙', 'legislative council election', 'legco election',
            '国家安全公署', 'national security office', 'nsa', 'nsf', 'national security law',
            '国安法', '国家安全法', '国安公署'
        ]
        text_to_check = (title + ' ' + description + ' ' + news.get('full_content', '')).lower()
        if any(keyword.lower() in text_to_check for keyword in political_keywords):
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
        elif any(k in text for k in ['art', 'culture', 'entertainment', 'exhibition', 'drama', '文化', '藝術', '展覽', '演出', 
                                      'tvb', '生日', '婚紗', '停播', '節目', '電視', '明星', '演員', '生日', '封盤']):
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
    
    # 3. バランス選択（優先順位に基づいて20-25件選択）
    selected = []
    target_count = 22  # 20-25件の中央値（API制限を考慮）
    
    # カテゴリーごとの優先順位（ユーザー指定順）
    priority_cats = [
        'ビジネス・経済',      # 1位: 46件
        '社会・その他',        # 2位: 19件  
        'カルチャー',          # 3位: 15件
        '不動産',             # 4位: 13件
        '政治・行政',          # 5位: 8件
        '医療・健康',          # 6位: 3件
        '治安・犯罪',          # 7位: 6件
        'テクノロジー',        # 8位: 76件
        '事故・災害',          # 9位: 1件
        '交通'                # 10位: 1件
    ]
    
    # 各カテゴリーから優先順位に基づいて選択
    for cat in priority_cats:
        if cat in categorized and categorized[cat]:
            # 各カテゴリーから最大何件取るかを計算（API制限を考慮して調整）
            if cat == 'ビジネス・経済':
                max_count = min(5, len(categorized[cat]))  # 1位: 5件
            elif cat == '社会・その他':
                max_count = min(4, len(categorized[cat]))  # 2位: 4件
            elif cat == 'カルチャー':
                max_count = min(3, len(categorized[cat]))  # 3位: 3件
            elif cat == '不動産':
                max_count = min(3, len(categorized[cat]))  # 4位: 3件
            elif cat == '政治・行政':
                max_count = min(2, len(categorized[cat]))  # 5位: 2件
            elif cat == '医療・健康':
                max_count = min(2, len(categorized[cat]))  # 6位: 2件
            elif cat == '治安・犯罪':
                max_count = min(2, len(categorized[cat]))  # 7位: 2件
            elif cat == 'テクノロジー':
                max_count = min(1, len(categorized[cat]))  # 8位: 1件
            else:
                max_count = min(1, len(categorized[cat]))  # 9-10位: 1件
            
            # 選択
            for i in range(max_count):
                if categorized[cat] and len(selected) < target_count:
                    selected.append(categorized[cat].pop(0))
            
            if len(selected) >= target_count:
                break
    
    # まだ足りない場合は残りのカテゴリーから追加
    if len(selected) < target_count:
        for cat in priority_cats:
            if cat in categorized and categorized[cat]:
                while categorized[cat] and len(selected) < target_count:
                    selected.append(categorized[cat].pop(0))
                if len(selected) >= target_count:
                    break
    
    print(f"\n✅ 選択完了: {len(selected)}件（優先順位調整済み）")
    
    # 選択されたニュースのカテゴリー別内訳を表示
    selected_categories = defaultdict(int)
    for news in selected:
        category = news.get('category', '未分類')
        selected_categories[category] += 1
    
    print("📊 選択されたニュースのカテゴリー別内訳:")
    for cat in priority_cats:
        if cat in selected_categories:
            print(f"  {cat}: {selected_categories[cat]}件")
    
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
    
    generator = GrokArticleGenerator()
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
