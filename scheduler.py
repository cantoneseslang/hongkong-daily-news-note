#!/usr/bin/env python3
"""
香港ニュース自動投稿スケジューラー
毎日指定時刻に自動実行
"""

import schedule
import time
import json
from datetime import datetime, timedelta, timezone
import subprocess
import sys
from pathlib import Path

# HKTタイムゾーン（UTC+8）
HKT = timezone(timedelta(hours=8))

class NewsScheduler:
    def __init__(self, config_path: str = "config.json", schedule_time: str = "06:00"):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.schedule_time = self.config.get('settings', {}).get('schedule_time', schedule_time)
        except:
            self.schedule_time = schedule_time
            self.config = {}
    
    def run_daily_job(self):
        """毎日実行するジョブ"""
        print("\n" + "=" * 70)
        print(f"🕐 香港ニュース自動投稿ジョブ開始")
        print(f"⏰ 実行時刻: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        try:
            # 1. ニュース取得（RSSフィード）
            print("\n📰 ステップ1: RSSフィードからニュース取得")
            result = subprocess.run(
                [sys.executable, "fetch_rss_news.py"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                print(f"❌ ニュース取得失敗: {result.stderr}")
                return
            
            print(result.stdout)
            
            # 最新のrss_news.jsonを取得
            rss_files = sorted(Path("daily-articles").glob("rss_news_*.json"))
            if not rss_files:
                print("❌ ニュースファイルが見つかりません")
                return
            
            latest_rss = rss_files[-1]
            print(f"✅ ニュースファイル: {latest_rss}")
            
            # 2. 記事生成（過去記事との重複チェック付き）
            print("\n✍️  ステップ2: 記事生成（Grok API + 重複チェック）")
            result = subprocess.run(
                [sys.executable, "generate_article.py", str(latest_rss)],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode != 0:
                print(f"❌ 記事生成失敗: {result.stderr}")
                return
            
            print(result.stdout)
            
            # 最新の記事を取得
            article_files = sorted(Path("daily-articles").glob("hongkong-news_*.md"))
            if not article_files:
                print("❌ 記事ファイルが見つかりません")
                return
            
            latest_article = article_files[-1]
            print(f"✅ 記事ファイル: {latest_article}")
            
            # 3. 日付の自動修正
            print("\n📅 ステップ3: 記事タイトルの日付を修正")
            import re
            with open(latest_article, 'r', encoding='utf-8') as f:
                content = f.read()
            
            today = datetime.now(HKT).strftime('%Y年%m月%d日')
            # タイトルの日付を今日の日付に修正
            content = re.sub(
                r'# 毎日AI香港ピックアップニュース\(\d{4}年\d{2}月\d{2}日\)',
                f'# 毎日AI香港ピックアップニュース({today})',
                content
            )
            
            with open(latest_article, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ タイトル日付を {today} に修正しました")
            
            # 4. 完了メッセージ
            print("\n" + "=" * 70)
            print("✅ 記事生成完了！")
            print("=" * 70)
            print(f"""
📁 記事パス: {latest_article}
📅 記事日付: {today}
📊 重複チェック: 過去3日分の記事と比較済み

💡 note投稿は手動で行ってください:
   cd /Users/sakonhiroki/note-post-mcp
   node auto-login-and-draft.js {latest_article}
""")
            
            print("=" * 70)
            print("✅ ジョブ完了")
            print("=" * 70)
            
        except subprocess.TimeoutExpired:
            print("❌ タイムアウト: 処理に時間がかかりすぎました")
        except Exception as e:
            print(f"❌ エラー発生: {e}")
    
    def start(self, run_now: bool = False):
        """スケジューラー開始"""
        print("\n🚀 香港ニュース自動投稿スケジューラー起動")
        print("=" * 70)
        print(f"⏰ 実行時刻: 毎日 {self.schedule_time}")
        print(f"🌍 システムタイムゾーン: Asia/Hong_Kong")
        print("=" * 70)
        
        if run_now:
            print("\n💡 テスト実行を今すぐ開始します...\n")
            # 初回テスト実行
            self.run_daily_job()
        else:
            print("\n💤 スケジュール待機中...")
        
        # スケジュール設定
        schedule.every().day.at(self.schedule_time).do(self.run_daily_job)
        
        print(f"\n⏰ 次回実行予定: {schedule.next_run()}")
        print("\n🔄 スケジューラー稼働中... (Ctrl+C で停止)")
        
        # メインループ
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1分ごとにチェック
        except KeyboardInterrupt:
            print("\n\n👋 スケジューラーを停止しました")
            sys.exit(0)

if __name__ == "__main__":
    scheduler = NewsScheduler()
    scheduler.start()

