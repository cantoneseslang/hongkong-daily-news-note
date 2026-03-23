#!/usr/bin/env node
/**
 * 「いま開いている普通の Chrome」に近い体験で NOTE_SESSION_COOKIE を取る。
 *
 * 重要: すでに起動中の Chrome に、後から別アプリが勝手に中身を読むことは
 * Chrome の設計上できません（セキュリティ）。だから一度だけ、下のコマンドで
 * Chrome を「リモートデバッグ付き」で起動し直すか、普段と同じプロファイルを
 * 指定して起動します。
 *
 *   npm run note:cookie:cdp
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

function cookiesToHeader(cookies) {
  const byName = new Map();
  for (const c of cookies) {
    byName.set(c.name, c);
  }
  return [...byName.values()].map((c) => `${c.name}=${c.value}`).join('; ');
}

function isNoteDomain(domain) {
  const d = domain.replace(/^\./, '');
  return d === 'note.com' || /note\.com$/i.test(d);
}

async function main() {
  const outFile = path.resolve(process.argv[2] || path.join(repoRoot, '.note-session-cookie.txt'));

  console.log('');
  console.log('=== NOTE_SESSION_COOKIE（普通の Chrome 経由・CDP）===');
  console.log('');
  console.log('【なぜ「いま開いている Chrome」をそのまま使えないか】');
  console.log('  • 動いている Chrome に、Playwright などが後から接続する公式の穴はありません。');
  console.log('  • 同じプロファイルは「同時に1つの Chrome」しか開けません。');
  console.log('  • だから「リモートデバッグ付き」で Chrome を1回起動し直し、このスクリプトが');
  console.log('    その Chrome にだけ接続して Cookie を読みます（中身はあなたが普段と同じログイン）。');
  console.log('');
  console.log('【手順】まず Chrome をすべて終了（⌘Q）してから、次をターミナルにコピペ:');
  console.log('');
  console.log('  /Applications/Google\\\\ Chrome.app/Contents/MacOS/Google\\\\ Chrome \\\\');
  console.log('    --remote-debugging-port=9222 \\\\');
  console.log('    --user-data-dir=\"$HOME/Library/Application Support/Google/Chrome\"');
  console.log('');
  console.log('  ※ 上は「普段の Chrome と同じプロファイル」パス（macOS 標準）。');
  console.log('     うまくいかない場合は、別フォルダを指定してログインし直す方法もあります:');
  console.log('     --user-data-dir=\"$HOME/chrome-note-cdp-profile\"');
  console.log('');
  console.log('起動したウィンドウで note.com にログインし、https://editor.note.com/new まで開いてください。');
  console.log('  （メールで通らない場合は X(𝕏) 等のソーシャルログインでかまいません）');
  console.log('');
  console.log(`接続先: ${CDP_URL}`);
  console.log(`保存先: ${outFile}`);
  console.log('');

  await ask('準備ができたら Enter … ');

  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
  } catch (e) {
    console.error('');
    console.error('❌ CDP に接続できません:', e.message);
    console.error('   Chrome を --remote-debugging-port=9222 で起動したか確認してください。');
    process.exit(1);
  }

  try {
    const contexts = browser.contexts();
    const all = [];
    for (const ctx of contexts) {
      all.push(...(await ctx.cookies()));
    }
    const noteCookies = all.filter((c) => isNoteDomain(c.domain));
    const header = cookiesToHeader(noteCookies);

    if (!header || !header.includes('note_session')) {
      console.log('');
      console.log('⚠️  note_session が見つかりません。ログインできているか確認してください。');
      const ok = await ask('それでも保存しますか？ (y/N) ');
      if (String(ok).trim().toLowerCase() !== 'y') {
        process.exit(1);
      }
    }

    writeFileSync(outFile, header, 'utf-8');
    console.log('');
    console.log('✅ 保存しました:', outFile);
    console.log('');
    console.log('GitHub → Secrets → NOTE_SESSION_COOKIE に中身を貼り付け。');
    console.log('（先頭 60 文字）', header.slice(0, 60) + (header.length > 60 ? '…' : ''));
    console.log('');
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
