#!/usr/bin/env node
/**
 * 手動で起動した「普通の Chrome」に CDP で接続し、Playwright 形式の storageState を保存する。
 * Playwright がブラウザを起動すると note に弾かれる場合の回避策。
 *
 * 使い方:
 *   1) 別ターミナルで Chrome を次のように起動（ポートは環境変数で変更可）:
 *      macOS:
 *        /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
 *          --remote-debugging-port=9222 \
 *          --user-data-dir="$HOME/chrome-note-cdp-profile"
 *   2) その Chrome ウィンドウだけで https://note.com にログイン → editor まで開く
 *   3) このリポジトリで:
 *        npm run note:auth:cdp
 *
 * 接続先: NOTE_CDP_URL（既定 http://127.0.0.1:9222）
 */

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import * as readline from 'readline';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');
const CDP_URL = process.env.NOTE_CDP_URL || 'http://127.0.0.1:9222';

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) =>
    rl.question(question, (ans) => {
      rl.close();
      resolve(ans);
    })
  );
}

async function main() {
  const outPath = path.resolve(process.argv[2] || path.join(repoRoot, '.note-auth-state.json'));

  console.log('');
  console.log('=== NOTE_AUTH_STATE 取得（CDP・手動 Chrome）===');
  console.log('');
  console.log('【事前】別ターミナルで Chrome を次で起動してください（コピペ可）:');
  console.log('');
  console.log('  # macOS');
  console.log('  /Applications/Google\\\\ Chrome.app/Contents/MacOS/Google\\\\ Chrome \\\\');
  console.log('    --remote-debugging-port=9222 \\\\');
  console.log('    --user-data-dir=\"$HOME/chrome-note-cdp-profile\"');
  console.log('');
  console.log('起動した Chrome だけで note にログインし、https://editor.note.com/new まで進めてください。');
  console.log('（普段の Chrome プロファイルとは別フォルダなので、初回はログインが必要です）');
  console.log('');
  console.log(`接続先: ${CDP_URL}`);
  console.log(`保存先: ${outPath}`);
  console.log('');

  await ask('準備ができたら Enter を押してください... ');

  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
  } catch (e) {
    console.error('');
    console.error('❌ CDP に接続できません:', e.message);
    console.error('   Chrome を --remote-debugging-port=9222 で起動しているか確認してください。');
    process.exit(1);
  }

  try {
    const contexts = browser.contexts();
    if (!contexts.length) {
      throw new Error('ブラウザコンテキストがありません');
    }
    // 通常は最初のコンテキストに note の Cookie が入っている
    const context = contexts[0];
    const storageState = await context.storageState();
    const pretty = JSON.stringify(storageState, null, 2);
    const oneLine = JSON.stringify(storageState);

    writeFileSync(outPath, pretty, 'utf-8');
    const compactPath = outPath.replace(/\.json$/i, '') + '.compact.json';
    writeFileSync(compactPath, oneLine, 'utf-8');

    console.log('');
    console.log('✅ 保存しました:');
    console.log(`   ${outPath}`);
    console.log(`   ${compactPath}`);
    console.log('');
    console.log('GitHub → Settings → Secrets → NOTE_AUTH_STATE に .compact.json の中身を貼り付け。');
    console.log('');
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
