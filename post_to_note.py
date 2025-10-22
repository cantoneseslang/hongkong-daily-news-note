#!/usr/bin/env python3
"""
生成した記事をnote.comに投稿する準備
※ このスクリプトはnote-post-mcpプロジェクトとは完全に独立しています
"""

import json
import sys
from pathlib import Path

class NotePublisher:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.note_config = self.config['note']
    
    def publish_to_note(self, markdown_path: str) -> bool:
        """note投稿の準備（手動投稿のための情報表示）"""
        print("\n📮 note投稿準備")
        print("=" * 60)
        
        print(f"📝 記事パス: {markdown_path}")
        print(f"🔐 認証ファイル: {self.note_config['state_path']}")
        
        print("""
📋 note投稿方法（以下から選択してください）:

【方法1】Cursor MCP経由（推奨）
  Cursorで以下のMCPコマンドを実行:
  
  mcp_note-post-mcp_save_draft({
    "markdown_path": "%s",
    "state_path": "%s",
    "timeout": %d
  })

【方法2】手動コピー＆ペースト
  1. 上記の記事ファイルを開く
  2. 内容をコピー
  3. https://note.com/creator で新規記事作成
  4. 貼り付けて投稿

詳細は manual_post_to_note.md を参照してください。
""" % (markdown_path, 
       self.note_config['state_path'],
       self.note_config['timeout']))
        
        return True
    
    def validate_markdown(self, markdown_path: str) -> bool:
        """Markdownファイルの検証"""
        path = Path(markdown_path)
        if not path.exists():
            print(f"❌ ファイルが存在しません: {markdown_path}")
            return False
        
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if len(content) < 100:
            print("❌ 記事が短すぎます（100文字未満）")
            return False
        
        # タイトルチェック（最初の行が # で始まる）
        if not content.strip().startswith('#'):
            print("⚠️  タイトル（# で始まる行）がありません")
        
        print("✅ Markdown検証完了")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python post_to_note.py <article.md>")
        sys.exit(1)
    
    markdown_file = sys.argv[1]
    
    publisher = NotePublisher()
    
    if publisher.validate_markdown(markdown_file):
        publisher.publish_to_note(markdown_file)
        print("\n✅ 投稿準備完了！")
    else:
        print("\n❌ 投稿に失敗しました")
        sys.exit(1)

