# 記事再生成ガイド

## 今日の記事を再生成する

GitHub Actionsで生成された記事に問題がある場合、以下のコマンドで手動で再生成できます。

### 基本的な使い方

```bash
# 今日の記事を再生成
./regenerate_today.sh
```

### 特定の日付の記事を再生成

```bash
# 例: 2025年11月19日の記事を再生成
./regenerate_today.sh 2025-11-19
```

### 実行前の確認事項

1. **仮想環境がアクティブになっているか確認**
   ```bash
   source venv/bin/activate
   ```

2. **config.jsonが存在するか確認**
   ```bash
   ls -l config.json
   ```
   
   存在しない場合は、`config.local.json`をコピー：
   ```bash
   cp config.local.json config.json
   ```

3. **必要な権限を確認**
   ```bash
   chmod +x regenerate_today.sh
   ```

### トラブルシューティング

#### エラー: `No RSS news file found`

RSS ニュースの取得に失敗しています。手動で実行：

```bash
python fetch_rss_news.py
```

#### エラー: `Article generation failed`

記事生成に失敗しています。詳細を確認：

```bash
# 最新のRSSファイルを確認
ls -lt daily-articles/rss_news_*.json | head -1

# 手動で記事生成を実行
python generate_article.py daily-articles/rss_news_<日付>.json
```

#### 天気情報が不完全

修正済みのコードで再生成してください。以下の改善が含まれています：

- LLMの翻訳プロンプトを強化
- 長いテキストの自動分割
- トークン数の増加（2048→4096）
- タイトルと本文の分離翻訳

## 修正内容の詳細

### `generate_article.py`の改善

1. **天気翻訳の改善**
   - 完全な日本語翻訳を保証
   - 英語、広東語、中国語が残らないように改善
   - 文章の途中で切れないように改善

2. **エラーハンドリングの強化**
   - 翻訳エラー時の詳細なログ出力
   - フォールバック処理の改善

### 再生成スクリプトの機能

`regenerate_today.sh`は以下を実行します：

1. 既存の記事ファイルをバックアップ
2. RSS ニュースの取得
3. 記事の生成
4. 生成結果の検証とサマリー表示

## GitHub Actionsの実行確認

### 実行スケジュール

- **毎日 UTC 22:00（HKT 06:00）** に自動実行
- **手動実行も可能**（Actions タブから "Run workflow" をクリック）

### 実行ログの確認

1. GitHubリポジトリの「Actions」タブを開く
2. 最新の "Daily Hong Kong News Generator" ワークフローをクリック
3. 各ステップのログを確認

### よくある問題

1. **記事生成が失敗する**
   - API キーが正しく設定されているか確認
   - クレジットが残っているか確認（Grok API）

2. **note.com への投稿が失敗する**
   - NOTE_EMAIL, NOTE_PASSWORD が正しく設定されているか確認
   - NOTE_AUTH_STATE が最新か確認

3. **日付がずれる**
   - タイムゾーンが `Asia/Hong_Kong` に設定されているか確認
   - ワークフローの実行時刻が正しいか確認

## サポート

問題が解決しない場合は、以下の情報を含めて報告してください：

- エラーメッセージ
- 実行したコマンド
- `config.json`の内容（APIキーは除く）
- 最新のログファイル

```bash
# ログファイルの確認
ls -lt logs/
```

