#!/usr/bin/env python3
"""
香港ニュース記事生成スクリプト（広東語学習セクション付き）

【絶対変更禁止警告】天気情報翻訳処理について
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  ⚠️  ⚠️  緊急警告：このセクションは絶対に変更しないでください！⚠️  ⚠️  ⚠️

このファイルには、天気情報の広東語/中文を日本語に翻訳する重要な処理が含まれています。
このコードはGitHub Actionsで動作確認済みです。変更すると必ず問題が再発します。

【絶対変更禁止セクション - 変更する場合は必ずユーザーに確認】
- format_weather_info() メソッド
- _llm_translate_text() メソッド  
- _has_chinese_chars() メソッド
- _is_already_japanese() メソッド

【過去の問題履歴 - 何度も同じ問題が再発】
- コードを「微調整」→ 毎回広東語混在問題が再発
- デバッグログ追加 → 動作が変わる
- フォールバック処理追加 → 複雑になり問題発生
- エラーハンドリング変更 → 広東語が表示される

【変更しようとしているAIアシスタントへ】
このセクションを変更しようとしている場合：
1. 変更を即座に中止してください
2. ユーザーに確認を取ってください
3. 「動作確認済みのコード」を変更する理由を明確に説明してください
4. 変更が必要な場合でも、最小限の変更にとどめてください

【必須機能（削除禁止）】
1. リトライ処理（最大3回） - 削除すると一時的なAPIエラーで広東語が表示される
2. 翻訳結果の検証処理（_has_chinese_chars） - 削除すると不完全な翻訳が通る
3. エラーハンドリング（原文を返さない処理） - 削除すると広東語が記事に表示される

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import requests
import re
import time
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

【重要】今日の日付は {today_date}（{today_date_iso}）です。タイトルには必ず「毎日AIピックアップニュース({today_date})」という形式を使用してください。

{news_text}

記事の要件：
1. タイトルは必ず「# 毎日AIピックアップニュース({today_date})」という形式で記載してください
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
        
        # 本文を抽出（タイトル行を除く）
        if lines and lines[0].startswith('#'):
            body = '\n'.join(lines[1:])
        else:
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
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 【重要・変更禁止】天気情報翻訳処理
    # ═══════════════════════════════════════════════════════════════════════════════
    # 
    # 【警告】このセクションは絶対に変更・削除・コメントアウトしないでください！
    # 
    # 重要理由：
    # 1. 広東語/中文の天気情報を日本語に翻訳する必須処理です
    # 2. 過去に何度も問題が再発しており、この処理を変更すると必ず広東語が混在します
    # 3. 翻訳失敗時に原文を返すと、記事に広東語がそのまま表示される致命的な問題が発生します
    # 
    # 変更履歴による問題の再発：
    # - このコードを「微調整」すると、毎回広東語問題が再発しています
    # - リトライ処理、検証処理、エラーハンドリングは必須です
    # - フォールバックで原文を返す処理は絶対に追加しないでください
    # 
    # 変更が必要な場合：
    # 1. 必ずこのコメント全体を読んでから変更してください
    # 2. 変更前後で翻訳処理が確実に実行されることを確認してください
    # 3. 広東語/中文の検証処理を削除しないでください
    # 4. エラー時に原文を返す処理を追加しないでください
    # 
    # ═══════════════════════════════════════════════════════════════════════════════
    def format_weather_info(self, weather_data: Dict) -> str:
        """天気情報をMarkdown形式に整形（変更禁止：広東語翻訳の必須処理）"""
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
        
        # 地域天気予報のみ処理
        if 'weather_forecast' not in weather_data:
            return ""
        
        forecast = weather_data['weather_forecast']
        title = forecast.get('title', 'N/A')
        desc = clean_weather_text(forecast.get('description', ''))
        
        # 天気情報はLLMで一括日本語翻訳（辞書置換は使わない）
        translated_title = self._llm_translate_text(title)
        translated_desc = self._llm_translate_text(desc)
        
        # 【絶対必須】エラー表示は記事に出さない
        if '[翻訳エラー' in translated_title or '[翻訳エラー' in translated_desc:
            return ""

        # Descriptionは厳格に日本語判定（失敗ならセクションごと非表示）
        if not self._is_japanese(translated_desc):
            return ""

        # Titleは短文・漢字比率が高くても許容。弱い場合は安全な日本語タイトルに差し替え
        if not self._is_japanese_title(translated_title):
            translated_title = "香港天文台が発表した天気予報"
        
        # 翻訳成功時のみ天気予報セクションを返す（ミッション：中国語を日本語に翻訳された記事を投稿）
        weather_section = f"## 本日の香港の天気\n\n### 天気予報\n{translated_title}\n{translated_desc}\n\n**引用元**: 香港天文台"
        return weather_section
    
    def _translate_weather_text(self, text: str) -> str:
        """レガシー互換（未使用）。LLMベース翻訳に切替済み。"""
        return self._llm_translate_text(text)

    # ═══════════════════════════════════════════════════════════════════════════════
    # 【重要・変更禁止】広東語/中文翻訳処理のコア関数
    # ═══════════════════════════════════════════════════════════════════════════════
    # 
    # 【警告】この関数は絶対に変更・簡略化しないでください！
    # 
    # 重要ポイント：
    # 1. リトライ処理（最大3回）は必須です
    # 2. 翻訳結果の検証（_has_chinese_chars）は必須です
    # 3. エラー時に原文を返す処理は絶対に追加しないでください
    # 4. エラーメッセージを返すことで、広東語混在を防ぎます
    # 
    # 過去の問題：
    # - リトライ処理を削除 → 翻訳失敗で広東語が残る
    # - 検証処理を削除 → 不完全な翻訳が通る
    # - エラー時に原文を返す → 必ず広東語が記事に表示される
    # 
    # ═══════════════════════════════════════════════════════════════════════════════
    def _llm_translate_text(self, text: str) -> str:
        """LLMで広東語/中文を自然な日本語に一発翻訳（日本語以外混在禁止）"""
        if not text:
            return ""
        
        prompt = (
            "以下の広東語/中文テキストを自然な日本語に翻訳してください。"\
            "記号や数値は保持し、日本語以外（中文の語彙・句読点・英語）が残らないように。\n\n" + text
        )

        # 【絶対必須】フォールバック機構：Gemini → Claude → Grok の順で試行
        # ミッション：翻訳を100%成功させる（いずれかのAPIで必ず成功させる）
        # APIキーがあるAPIのみを優先順位順に追加
        apis_to_try = []
        
        # 優先順位1: Gemini API（APIキーがある場合のみ）
        if 'gemini_api' in self.config and self.config['gemini_api'].get('api_key') and self.config['gemini_api']['api_key'].strip():
            apis_to_try.append(('gemini', self.config['gemini_api']['api_key'], 
                               self.config['gemini_api']['api_url'], True))
        
        # 優先順位2: Claude API（APIキーがある場合のみ）
        if 'claude_api' in self.config and self.config['claude_api'].get('api_key') and self.config['claude_api']['api_key'].strip():
            apis_to_try.append(('claude', self.config['claude_api']['api_key'], 
                               self.config['claude_api']['api_url'], False))
        
        # 優先順位3: Grok API（APIキーがある場合のみ）
        if 'grok_api' in self.config and self.config['grok_api'].get('api_key') and self.config['grok_api']['api_key'].strip():
            apis_to_try.append(('grok', self.config['grok_api']['api_key'], 
                               self.config['grok_api']['api_url'], None))
        
        # 試行するAPIがない場合はエラー
        if not apis_to_try:
            print(f"❌ 有効なAPIキーがありません。翻訳できません。")
            return "[翻訳エラー: 天気情報の翻訳に失敗しました]"
        
        # 各APIで順番に試行
        for api_name, api_key, api_url, use_gemini_flag in apis_to_try:
            if not api_key:
                continue
                
            try:
                if use_gemini_flag is True:
                    headers = {"Content-Type": "application/json"}
                    api_url_with_key = f"{api_url}?key={api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
                    }
                    resp = requests.post(api_url_with_key, headers=headers, json=payload, timeout=60)
                    if resp.status_code == 200:
                        txt = resp.json()['candidates'][0]['content']['parts'][0]['text']
                        translated = txt.strip()
                        if self._is_japanese(translated):
                            print(f"✅ 天気翻訳成功 ({api_name})")
                            return translated
                        else:
                            print(f"⚠️  {api_name}翻訳結果が日本語として不十分。次のAPIを試行...")
                            continue
                    else:
                        print(f"⚠️  天気翻訳エラー ({api_name}): HTTP {resp.status_code}")
                        continue
                else:
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    if use_gemini_flag is False:
                        payload = {"model": "claude-3-5-sonnet-20241022", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 2048}
                    else:
                        payload = {"model": "grok-beta", "messages": [{"role": "system", "content": "Translate to natural Japanese only."}, {"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 2048}
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
                    if resp.status_code == 200:
                        if use_gemini_flag is False:
                            txt = resp.json()['content'][0]['text']
                        else:
                            txt = resp.json()['choices'][0]['message']['content']
                        translated = txt.strip()
                        if self._is_japanese(translated):
                            print(f"✅ 天気翻訳成功 ({api_name})")
                            return translated
                        else:
                            print(f"⚠️  {api_name}翻訳結果が日本語として不十分。次のAPIを試行...")
                            continue
                    else:
                        print(f"⚠️  天気翻訳エラー ({api_name}): HTTP {resp.status_code}")
                        continue
            except Exception as e:
                print(f"⚠️  天気翻訳エラー ({api_name}): {e}")
                continue
        
        # すべてのAPIで失敗した場合
        print(f"❌ すべてのAPIで天気翻訳が失敗しました。原文を返却しません。")
        return "[翻訳エラー: 天気情報の翻訳に失敗しました]"
    
    # 【重要・変更禁止】広東語/中文検証関数
    # これらの関数を削除・無効化すると、翻訳失敗を検出できず広東語が残ります
    def _has_chinese_chars(self, text: str) -> bool:
        """テキストに広東語/中文文字が含まれているかチェック（変更禁止）"""
        import re
        # 繁体字・簡体字の範囲をチェック（Unicode範囲: \u4e00-\u9fff）
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        return bool(chinese_pattern.search(text))
    
    def _is_japanese(self, text: str) -> bool:
        """翻訳結果が日本語かどうかチェック（ひらがな・カタカナが11文字以上含まれているか）（変更禁止）"""
        import re
        # ひらがな（\u3040-\u309F）またはカタカナ（\u30A0-\u30FF）の文字数をカウント
        hiragana_katakana_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')
        matches = hiragana_katakana_pattern.findall(text)
        count = len(matches)
        # 11文字以上の場合のみ日本語と判定
        return count >= 11
    
    def _is_japanese_title(self, text: str) -> bool:
        """タイトル用の緩和判定：ひらがな/カタカナ1文字以上、または日本語キーワードを含む"""
        if not text:
            return False
        import re
        kana_count = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', text))
        if kana_count >= 1:
            return True
        keywords = ['天気', '天気予報', '気象', '香港天文台', '予報', '天候']
        return any(k in text for k in keywords)
    def _is_already_japanese(self, text: str) -> bool:
        """テキストが既に日本語のみかチェック（広東語/中文が含まれていない）（変更禁止）"""
        return not self._has_chinese_chars(text)
    
    def _generate_cantonese_section(self) -> str:
        """広東語学習者向けの定型文を生成（固定内容・変更禁止）"""
        # この定型文は記事の最後に必ず追加される固定内容です
        # 内容を変更しないでください
        return """## 広東語学習者向け情報

広東語学習者向けにLINEが良い、便利という方もいるでしょうから、スラング先生公式アカウントもありますのでこちらご登録してから使用してください。こちらもLEDのチャットbot形式で秘書のリーさんが広東語についてなんでも回答してくれますのでぜひ使ってみてください

(今現在400名以上の方に登録していただいております）

[![スラング先生公式LINE](shared/line-img1.jpg)](https://line.me/R/ti/p/@298mwivr)

[![LINEでお問合せ](shared/line-qr.png)](https://line.me/R/ti/p/@298mwivr)

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
        seen_titles = []  # 類似度判定用に保持
        seen_urls = set()  # 正規化URLの重複排除
        duplicate_count = 0
        
        def _normalize_title(t: str) -> str:
            return re.sub(r'[^\w\s]', '', t.lower()).strip()
        
        for article in articles[1:]:
            lines = article.split('\n')
            title = lines[0].strip() if lines else ''
            norm_title = _normalize_title(title)
            
            # セクション内の最初の独立URL行を抽出
            block = '### ' + article
            url_match = re.search(r'(?m)^(https?://\S+)$', block)
            if url_match:
                from urllib.parse import urlparse, urlunparse
                try:
                    p = urlparse(url_match.group(1))
                    norm_url = urlunparse((p.scheme, p.netloc, p.path, '', '', ''))
                except Exception:
                    norm_url = url_match.group(1)
            else:
                norm_url = None
            
            # URL重複で除外
            if norm_url and norm_url in seen_urls:
                duplicate_count += 1
                continue
            
            # タイトルが短すぎる場合はそのまま許容
            if len(norm_title) < 10:
                result.append(article)
                if norm_url:
                    seen_urls.add(norm_url)
                seen_titles.append(norm_title)
                continue
            
            # 既存タイトルと類似度0.6以上なら重複として除外
            is_dup = False
            for st in seen_titles:
                if calculate_title_similarity(norm_title, st) >= 0.6:
                    is_dup = True
                    break
            if is_dup:
                duplicate_count += 1
                continue
            
            result.append(article)
            seen_titles.append(norm_title)
            if norm_url:
                seen_urls.add(norm_url)
        
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

def normalize_url(url: str) -> str:
    """URLを正規化（クエリパラメータを除去してベースURLのみ抽出）"""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        # クエリパラメータとフラグメントを除去
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return normalized
    except:
        # パース失敗時は元のURLを返す
        return url

def calculate_title_similarity(title1: str, title2: str) -> float:
    """2つのタイトルの類似度を計算（0.0-1.0）"""
    import re
    
    def normalize_title(t):
        # タイトルを正規化（小文字化、記号除去、単語分割）
        t = t.lower()
        t = re.sub(r'[^\w\s]', '', t)
        return set(t.split())
    
    words1 = normalize_title(title1)
    words2 = normalize_title(title2)
    
    if not words1 or not words2:
        return 0.0
    
    # 共通単語の数
    common_words = words1 & words2
    if len(common_words) < 3:
        return 0.0
    
    # Jaccard類似度（共通単語 / 全単語）
    all_words = words1 | words2
    similarity = len(common_words) / len(all_words) if all_words else 0.0
    
    # より厳密なチェック: 共通率が60%以上かつ、短い方のタイトルの70%以上が共通
    min_length = min(len(words1), len(words2))
    if min_length > 0:
        coverage = len(common_words) / min_length
        if similarity >= 0.6 and coverage >= 0.7:
            return similarity
    
    return 0.0

def preprocess_news(news_list):
    """ニュースの事前処理：重複除外、カテゴリー分類、バランス選択"""
    import re
    import os
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    # 0. 過去の記事ファイルから既出ニュースを抽出
    past_urls = set()  # 正規化されたURLのセット
    past_urls_original = set()  # 元のURLも保持（抽出用）
    past_titles = []
    
    # 過去7日分の記事ファイルをチェック（3日→7日に延長）
    for days_ago in range(1, 8):
        past_date = datetime.now(HKT) - timedelta(days=days_ago)
        past_file = f"daily-articles/hongkong-news_{past_date.strftime('%Y-%m-%d')}.md"
        
        if os.path.exists(past_file):
            print(f"📂 過去記事チェック: {past_file}")
            try:
                with open(past_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # URLを抽出（複数の形式に対応）
                    # 形式1: **リンク**: https://...（同じ行）
                    url_matches1 = re.findall(r'\*\*リンク\*\*:\s*(https?://[^\s\n]+)', content)
                    # 形式2: **リンク**: の後の独立行のURL（改行後すぐのURL）
                    url_matches2 = re.findall(r'\*\*リンク\*\*:[^\n]*\n+\n*(https?://[^\s\n]+)', content)
                    # 形式3: **引用元**: の後の独立行のURL（最も一般的な形式、改行後にURLが来る）
                    url_matches3 = re.findall(r'\*\*引用元\*\*:[^\n]+\n+\n*(https?://[^\s\n]+)', content)
                    # 形式4: ### 見出しの後の段落で、**引用元**: または **リンク**: の直後に来る独立行のURL
                    url_matches4 = re.findall(r'(?:\*\*引用元\*\*:|\*\*リンク\*\*:)[^\n]*(?:\n+)(https?://[^\s\n]+)', content)
                    
                    all_urls = url_matches1 + url_matches2 + url_matches3 + url_matches4
                    # 重複を除去（同じURLが複数のパターンで抽出される可能性がある）
                    all_urls = list(set(all_urls))
                    for url in all_urls:
                        # 元のURLも保持
                        past_urls_original.add(url.strip())
                        # 正規化したURLを追加
                        normalized = normalize_url(url.strip())
                        if normalized:
                            past_urls.add(normalized)
                    
                    # タイトルを抽出（### の後のタイトル）
                    title_matches = re.findall(r'^### (.+)$', content, re.MULTILINE)
                    # 天気予報のタイトルは除外
                    filtered_titles = [t for t in title_matches if '天気' not in t and 'weather' not in t.lower() and '天気予報' not in t]
                    past_titles.extend(filtered_titles)
                    
                print(f"  ✓ 既出URL: {len(all_urls)}件（正規化後: {len(past_urls)}件）、既出タイトル: {len(filtered_titles)}件")
            except Exception as e:
                print(f"  ⚠️  ファイル読み込みエラー: {e}")
    
    if past_urls:
        print(f"🔍 過去記事から合計 {len(past_urls_original)} 件のURL（正規化後: {len(past_urls)}件）と {len(past_titles)} 件のタイトルを抽出")
    
    # 過去記事との重複を除外
    filtered_news = []
    duplicate_count = 0
    url_duplicate_count = 0
    title_duplicate_count = 0
    
    for news in news_list:
        url = news.get('url', '')
        title = news.get('title', '')
        description = news.get('description', '')
        
        # 天気関連のニュースを除外
        weather_keywords = ['気温', '天気', '天文台', '気象', '天候', 'temperature', 'weather', 'observatory', 'forecast', '℃', '度', 'tropical', 'storm', 'typhoon', '台風']
        if any(keyword in title.lower() or keyword in description.lower() for keyword in weather_keywords):
            duplicate_count += 1
            continue
        
        # URL重複チェック（正規化後のURLで比較）
        normalized_url = normalize_url(url)
        if normalized_url and normalized_url in past_urls:
            url_duplicate_count += 1
            duplicate_count += 1
            continue
        
        # タイトル類似度チェック（類似度が0.6以上なら重複とみなす）
        is_similar = False
        for past_title in past_titles:
            similarity = calculate_title_similarity(title, past_title)
            if similarity >= 0.6:
                is_similar = True
                title_duplicate_count += 1
                break
        
        if is_similar:
            duplicate_count += 1
            continue
        
        filtered_news.append(news)
    
    if duplicate_count > 0:
        print(f"🚫 過去記事との重複除外: {duplicate_count}件（URL重複: {url_duplicate_count}件、タイトル類似: {title_duplicate_count}件）")
    
    print(f"📊 フィルタ後: {len(news_list)} → {len(filtered_news)}件")
    
    # 1. 同日内重複除外（URLとタイトルの両方でチェック）
    seen_titles_normalized = set()  # 正規化されたタイトル（高速チェック用）
    seen_titles_original = []  # 元のタイトル（類似度チェック用）
    seen_urls = set()  # 正規化されたURLのセット
    unique_news = []
    same_day_duplicates = 0
    same_day_url_duplicates = 0
    same_day_title_duplicates = 0
    
    def is_hk_related_news(item):
        title = item.get('title', '').lower()
        description = item.get('description', '').lower()
        url = item.get('url', '').lower()
        source = item.get('source', '').lower()
        positive = [
            'hong kong', 'hongkong', '香港', 'kowloon', '九龍', '新界', 'hksar', '尖沙咀', '灣仔', '中環', '旺角',
            '香港天文台', 'hong kong observatory', 'mtr', '港鐵', 'hkex', '香港交易所'
        ]
        if any(p in (title + ' ' + description) for p in positive):
            return True
        if any(seg in url for seg in ['/hong-kong', '/hongkong', '/news/hong-kong']) or '.hk/' in url:
            return True
        if any(s in source for s in ['rthk', 'hk01', 'hket', 'the standard', 'chinadaily hk', 'yahoo news hk']):
            return True
        if 'scmp' in source or 'scmp.com' in url:
            return ('/hong-kong' in url) or ('/hongkong' in url) or ('/news/hong-kong' in url)
        return False

    for news in filtered_news:
        url = news.get('url', '')
        title = news.get('title', '')
        normalized_title = re.sub(r'[^\w\s]', '', title.lower())
        normalized_url = normalize_url(url)
        
        # 香港関連以外は除外（SCMPビジネス等の世界記事の混入を防ぐ）
        if not is_hk_related_news(news):
            same_day_duplicates += 1
            continue

        # URL重複チェック
        is_url_duplicate = normalized_url and normalized_url in seen_urls
        
        # タイトル重複チェック（正規化後の完全一致）
        is_title_duplicate = normalized_title in seen_titles_normalized
        
        # タイトル類似度チェックも実行（既に追加済みのニュースと比較）
        if not is_title_duplicate:
            for existing_title in seen_titles_original:
                similarity = calculate_title_similarity(title, existing_title)
                if similarity >= 0.6:
                    is_title_duplicate = True
                    break
        
        if is_url_duplicate or is_title_duplicate:
            same_day_duplicates += 1
            if is_url_duplicate:
                same_day_url_duplicates += 1
            if is_title_duplicate:
                same_day_title_duplicates += 1
            continue
        
        # 重複なしの場合、リストに追加
        unique_news.append(news)
        seen_titles_normalized.add(normalized_title)
        seen_titles_original.append(title)  # 元のタイトルも保持
        if normalized_url:
            seen_urls.add(normalized_url)
    
    if same_day_duplicates > 0:
        print(f"📊 同日内重複除外: {len(filtered_news)} → {len(unique_news)}件（URL重複: {same_day_url_duplicates}件、タイトル類似: {same_day_title_duplicates}件）")
    
    # 2. イベントレベルのクラスタリング（同一出来事を1本に統合）
    clustered = []
    cluster_titles = []
    for item in unique_news:
        title = item.get('title', '')
        norm_title = re.sub(r'[^\w\s]', '', title.lower()).strip()
        is_same_event = False
        for ct in cluster_titles:
            if calculate_title_similarity(norm_title, ct) >= 0.85:
                is_same_event = True
                break
        if is_same_event:
            # 代表の情報量で置換（より本文/説明が長い方を採用）
            prev = clustered[-1]
            prev_len = len(prev.get('full_content', prev.get('description', '')))
            curr_len = len(item.get('full_content', item.get('description', '')))
            if curr_len > prev_len:
                clustered[-1] = item
                cluster_titles[-1] = norm_title
        else:
            clustered.append(item)
            cluster_titles.append(norm_title)
    print(f"🧮 イベント統合: {len(unique_news)} → {len(clustered)}件（タイトル類似≥0.85で1本化）")

    # 3. カテゴリー分類
    categorized = defaultdict(list)
    
    for news in clustered:
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
    
    # 4. バランス選択（厳しめ1本/イベント + バラエティ確保）
    selected = []
    target_count = 18
    max_per_source = 6
    per_source_counts = defaultdict(int)
    
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
    
    # 4-1. 各カテゴリーから最低1件ずつ（在庫があれば）
    for cat in priority_cats:
        if cat in categorized and categorized[cat]:
            for item in categorized[cat][:]:
                src = item.get('source', 'unknown')
                if per_source_counts[src] >= max_per_source:
                    continue
                selected.append(item)
                per_source_counts[src] += 1
                categorized[cat].remove(item)
                break
        if len(selected) >= target_count:
            break

    # 4-2. 優先順位に基づき残りを充当（ソース上限と在庫尊重）
    for cat in priority_cats:
        if len(selected) >= target_count:
            break
        if cat not in categorized or not categorized[cat]:
            continue
        for item in categorized[cat][:]:
            if len(selected) >= target_count:
                break
            src = item.get('source', 'unknown')
            if per_source_counts[src] >= max_per_source:
                continue
            selected.append(item)
            per_source_counts[src] += 1
            categorized[cat].remove(item)
    
    # 4-3. まだ足りない場合は残りから充当（ソース上限を維持）
    if len(selected) < target_count:
        for cat in priority_cats:
            if len(selected) >= target_count:
                break
            if cat not in categorized or not categorized[cat]:
                continue
            for item in categorized[cat][:]:
                if len(selected) >= target_count:
                    break
                src = item.get('source', 'unknown')
                if per_source_counts[src] >= max_per_source:
                    continue
                selected.append(item)
                per_source_counts[src] += 1
                categorized[cat].remove(item)
    
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

