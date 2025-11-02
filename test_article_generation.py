#!/usr/bin/env python3
"""
記事生成と天気予報翻訳のテストスクリプト
"""
import json
import sys
import os
import glob
from datetime import datetime, timedelta, timezone
import re

# HKTタイムゾーン
HKT = timezone(timedelta(hours=8))

def has_chinese_chars(text: str) -> bool:
    """テキストに広東語/中文文字が含まれているかチェック"""
    if not text:
        return False
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))

def test_article_generation():
    """記事生成と天気予報翻訳をテスト"""
    print("=" * 80)
    print("📋 記事生成と天気予報翻訳テスト")
    print("=" * 80)
    print()
    
    # 最新のRSSニュースJSONファイルを探す
    json_files = glob.glob("daily-articles/rss_news_*.json")
    if not json_files:
        print("❌ RSSニュースJSONファイルが見つかりません")
        return False
    
    # 最新のファイルを取得
    latest_file = max(json_files, key=os.path.getctime)
    print(f"📂 テスト対象ファイル: {latest_file}")
    print()
    
    # JSONファイルを読み込む
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ JSONファイル読み込みエラー: {e}")
        return False
    
    news_count = len(data.get('news', []))
    weather_data = data.get('weather', {})
    
    print(f"📊 ニュース件数: {news_count}件")
    print(f"🌤️  天気データ: {'あり' if weather_data else 'なし'}")
    print()
    
    # 天気データの詳細を表示
    if weather_data:
        print("🌤️  天気データの内容:")
        for key, value in weather_data.items():
            if isinstance(value, dict):
                title = value.get('title', 'N/A')
                desc = value.get('description', 'N/A')
                print(f"  {key}:")
                print(f"    タイトル: {title[:100]}...")
                print(f"    説明: {desc[:100] if desc else 'N/A'}...")
                
                # 広東語/中文が含まれているかチェック
                if has_chinese_chars(title) or has_chinese_chars(desc):
                    print(f"    ⚠️  広東語/中文が検出されました（これは正常：翻訳前のデータ）")
        print()
    
    # 記事生成を実行
    print("=" * 80)
    print("🚀 記事生成を実行します...")
    print("=" * 80)
    print()
    
    # generate_article.pyをインポートして実行
    try:
        from generate_article import GrokArticleGenerator, preprocess_news
        
        # コンフィグパスの決定
        config_path = os.environ.get('CONFIG_PATH')
        if not config_path:
            if os.path.exists('config.local.json'):
                config_path = 'config.local.json'
            else:
                config_path = 'config.json'
        
        print(f"📝 コンフィグファイル: {config_path}")
        print()
        
        # ニュースの事前処理
        print("📋 ニュースの事前処理中...")
        news_data = preprocess_news(data['news'])
        print(f"✅ 処理済みニュース: {len(news_data)}件")
        print()
        
        # 記事生成
        generator = GrokArticleGenerator(config_path)
        print("📝 記事生成中...")
        article = generator.generate_article(news_data)
        
        if not article:
            print("❌ 記事生成に失敗しました")
            return False
        
        print("✅ 記事生成完了")
        print()
        
        # 天気情報セクションを生成（実際の翻訳処理をテスト）
        print("=" * 80)
        print("🌤️  天気情報翻訳テスト")
        print("=" * 80)
        print()
        
        if weather_data:
            weather_section = generator.format_weather_info(weather_data)
            
            # 生成された天気情報を表示（最初の500文字）
            print("📄 生成された天気情報セクション（最初の500文字）:")
            print("-" * 80)
            print(weather_section[:500])
            if len(weather_section) > 500:
                print("...")
            print("-" * 80)
            print()
            
            # 広東語/中文が含まれているかチェック
            has_chinese = has_chinese_chars(weather_section)
            if has_chinese:
                print("❌ エラー: 天気情報セクションに広東語/中文が含まれています！")
                print()
                print("広東語/中文が含まれている箇所:")
                lines = weather_section.split('\n')
                for i, line in enumerate(lines, 1):
                    if has_chinese_chars(line):
                        print(f"  行{i}: {line[:100]}")
                return False
            else:
                print("✅ 天気情報セクションに広東語/中文は含まれていません")
                print()
        else:
            print("⚠️  天気データがありません（スキップ）")
            print()
        
        # 記事を保存（テスト用の一時ファイル）
        test_output_path = "daily-articles/test_output.md"
        saved_path = generator.save_article(article, weather_data, test_output_path)
        
        print("=" * 80)
        print("📄 生成された記事の確認")
        print("=" * 80)
        print()
        
        # 保存された記事を読み込んで確認
        with open(saved_path, 'r', encoding='utf-8') as f:
            article_content = f.read()
        
        # 記事全体に広東語/中文が含まれているかチェック
        print("🔍 記事全体の広東語/中文チェック...")
        has_chinese_in_article = has_chinese_chars(article_content)
        
        if has_chinese_in_article:
            print("❌ エラー: 記事全体に広東語/中文が含まれています！")
            print()
            print("広東語/中文が含まれている箇所:")
            lines = article_content.split('\n')
            chinese_lines = []
            for i, line in enumerate(lines, 1):
                if has_chinese_chars(line) and '天気' in line[:20]:
                    chinese_lines.append((i, line[:200]))
            
            if chinese_lines:
                for line_num, line_content in chinese_lines[:10]:  # 最初の10行
                    print(f"  行{line_num}: {line_content}")
            return False
        else:
            print("✅ 記事全体に広東語/中文は含まれていません")
            print()
        
        # 記事の基本情報を表示
        print("📊 記事の基本情報:")
        print(f"  タイトル: {article['title']}")
        print(f"  本文の長さ: {len(article['body'])}文字")
        print(f"  保存先: {saved_path}")
        print()
        
        # 天気情報セクションがあるか確認
        if "## 本日の香港の天気" in article_content:
            print("✅ 天気情報セクションが含まれています")
        else:
            print("⚠️  天気情報セクションが見つかりません")
        
        print()
        print("=" * 80)
        print("✅ すべてのテストが完了しました")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        import traceback
        print(f"❌ エラー発生: {e}")
        print()
        print("詳細:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_article_generation()
    sys.exit(0 if success else 1)

