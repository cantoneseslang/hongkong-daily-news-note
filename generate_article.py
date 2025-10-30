#!/usr/bin/env python3
"""
香港ニュース記事生成スクリプト（広東語学習セクション付き）
"""

import json
import requests
import re
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
- 引用元: **引用元**: ソース名
- リンク: **リンク**: URL
- 備考: **備考**: 説明（必要に応じて）

重要：JSON形式ではなく、Markdown形式で記事を生成してください。引用元とリンクは必ず別々の行に記載し、**で囲んでください。"""

        # ユーザープロンプト
        user_prompt = f"""以下の香港ニュースを日本語に翻訳し、記事として構成してください：

{news_text}

記事の要件：
1. 各ニュースを### 見出しで区切る
2. 内容を詳しく翻訳
3. 引用元、リンク、備考を適切に配置
4. 広告や宣伝文は除外
5. Markdown形式で出力

引用情報の形式（重要）：
- 引用元: **引用元**: ソース名（例：SCMP、RTHK等）
- リンク: **リンク**: URL（完全なURL）
- 備考: **備考**: 説明（必要に応じて）

各ニュースの最後に必ず引用元とリンクを別々の行で記載してください。

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
                    "model": "grok-beta",
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
                return self._parse_article_content(content)
                
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
    
    def _parse_article_content(self, content: str) -> Dict:
        """生成された記事コンテンツをパース"""
        # タイトルを抽出（最初の行）
        lines = content.split('\n')
        title = lines[0].replace('#', '').strip() if lines else "香港ニュース"
        
        # 本文を抽出
        body = content
        
        return {
            "title": title,
            "lead": "",
            "body": body,
            "tags": "香港,ニュース,最新,情報,アジア"
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
                if line:
                    cleaned_lines.append(line)
            return '\n'.join(cleaned_lines)
        
        weather_section = "## 本日の香港の天気\n"
        
        # 天気警報
        if 'weather_warning' in weather_data:
            warning = weather_data['weather_warning']
            title = warning.get('title', 'N/A')
            desc = clean_weather_text(warning.get('description', ''))
            
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
            "最高氣溫約": "最高気温約",
            "度": "度",
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

広東語学習者向けにLINEが良い、便利という方もいるでしょうから、スラング先生公式アカウントもありますのでこちらご登録してから使用してください。こちらもLEDのチャットbot形式で秘書のリーさんが広東語についてなんでも回答してくれますのでぜひ使ってみてください

(今現在400名以上の方に登録していただいております）

[スラング先生公式LINE](https://line.me/R/ti/p/@298mwivr)
![スラング先生公式LINE](https://raw.githubusercontent.com/cantoneseslang/hongkong-daily-news-note/main/shared/line-img1.jpg)

[LINEでお問合せ](https://line.me/R/ti/p/@298mwivr)
![LINEでお問合せ](https://raw.githubusercontent.com/cantoneseslang/hongkong-daily-news-note/main/shared/line-qr.png)

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
            (r'引用元:\s*([^:]+):\s*([^\s]+)', r'**引用元**: \1\n**リンク**: \2')
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
        seen_titles = set()
        duplicate_count = 0
        
        # 各記事をチェック
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
        
        # 広東語学習者向けの定型文を追加
        cantonese_section = self._generate_cantonese_section()
        
        # bodyの最初に改行を入れる（1行目が空行になり、ここに目次を挿入）
        markdown = f"""# {article['title']}

{content_str}

{cantonese_section}
----
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
        
        # URL重複チェック
        if url in past_urls:
            duplicate_count += 1
            continue
        
        # タイトル重複チェック（正規化）
        normalized_title = re.sub(r'[^\w\s]', '', title.lower())
        if any(re.sub(r'[^\w\s]', '', past_title.lower()) == normalized_title for past_title in past_titles):
            duplicate_count += 1
            continue
        
        filtered_news.append(news)
    
    if duplicate_count > 0:
        print(f"🚫 過去記事との重複除外: {duplicate_count}件")
    
    print(f"📊 フィルタ後: {len(news_list)} → {len(filtered_news)}件")
    
    # 1. 同日内重複除外
    seen_titles = set()
    unique_news = []
    same_day_duplicates = 0
    
    for news in filtered_news:
        title = news.get('title', '')
        normalized_title = re.sub(r'[^\w\s]', '', title.lower())
        
        if normalized_title not in seen_titles:
            seen_titles.add(normalized_title)
            unique_news.append(news)
        else:
            same_day_duplicates += 1
    
    if same_day_duplicates > 0:
        print(f"📊 同日内重複除外: {len(filtered_news)} → {len(unique_news)}件")
    
    # 2. カテゴリー分類
    categorized = defaultdict(list)
    
    for news in unique_news:
        title = news.get('title', '').lower()
        description = news.get('description', '').lower()
        content = f"{title} {description}"
        
        # カテゴリー判定
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
        elif any(keyword in content for keyword in ['文化', '芸能', 'スポーツ', '映画', '音楽', 'アート', 'culture', 'entertainment', 'sports', 'movie', 'music', 'art', 'イベント', '祭り', '伝統']):
            category = 'カルチャー'
        else:
            category = '社会・その他'
        
        categorized[category].append(news)
    
    print(f"\n📋 カテゴリー別件数:")
    for cat, items in sorted(categorized.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(items)}件")
    
    # 3. バランス選択（優先順位に基づいて15-20件選択）
    selected = []
    target_count = 18  # 15-20件に調整（API制限を考慮）
    
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
                max_count = min(4, len(categorized[cat]))  # 1位: 4件
            elif cat == '社会・その他':
                max_count = min(3, len(categorized[cat]))  # 2位: 3件
            elif cat == 'カルチャー':
                max_count = min(3, len(categorized[cat]))  # 3位: 3件
            elif cat == '不動産':
                max_count = min(2, len(categorized[cat]))  # 4位: 2件
            elif cat == '政治・行政':
                max_count = min(2, len(categorized[cat]))  # 5位: 2件
            elif cat == '医療・健康':
                max_count = min(2, len(categorized[cat]))  # 6位: 2件
            elif cat == '治安・犯罪':
                max_count = min(1, len(categorized[cat]))  # 7位: 1件
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
