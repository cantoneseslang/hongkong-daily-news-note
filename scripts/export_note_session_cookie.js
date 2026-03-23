#!/usr/bin/env node
/**
 * ブラウザをこちらで開く → あなたは note にログインするだけ → Cookie は自動でファイルに保存。
 * DevTools でコピーする必要はありません。
 *
 *   npm run note:cookie
 *
 * 出力: .note-session-cookie.txt（GitHub Secret NOTE_SESSION_COOKIE にそのまま貼れる1行）
 */

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import * as readline from 'readline';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

const STEALTH_CHROME_ARGS = [
  '--lang=ja-JP',
  '--disable-blink-features=AutomationControlled',
  '--disable-infobars',
  '--window-size=1280,800',
];

async function launchBrowser() {
  const launchOpts = {
    headless: false,
    args: [...STEALTH_CHROME_ARGS],
    ignoreDefaultArgs: ['--enable-automation'],
  };
  if (process.env.NOTE_AUTH_FORCE_CHROMIUM === '1') {
    return await chromium.launch({ headless: false, args: [...STEALTH_CHROME_ARGS] });
  }
  try {
    console.log('→ Google Chrome を開きます…');
    return await chromium.launch({ ...launchOpts, channel: 'chrome' });
  } catch (e) {
    console.log('⚠️ Chrome:', e.message);
  }
  try {
    return await chromium.launch({ ...launchOpts, channel: 'msedge' });
  } catch (e) {
    console.log('⚠️ Edge:', e.message);
  }
  return await chromium.launch({ headless: false, args: [...STEALTH_CHROME_ARGS] });
}

function ask(q) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(q, (a) => { rl.close(); resolve(a); }));
}

/** Playwright の cookie 配列を Cookie: ヘッダ用の1行にする */
function cookiesToHeader(cookies) {
  return cookies.map((c) => `${c.name}=${c.value}`).join('; ');
}

async function main() {
  const outFile = path.resolve(process.argv[2] || path.join(repoRoot, '.note-session-cookie.txt'));

  console.log('');
  console.log('=== NOTE_SESSION_COOKIE 自動取得 ===');
  console.log('');
  console.log('これからブラウザを開きます。');
  console.log('あなたがやること: 表示されたウィンドウで note にログインするだけ（二段階もここで）。');
  console.log('できれば https://editor.note.com/new まで開いてください。');
  console.log('終わったらこのターミナルで Enter を押してください → Cookie は自動でファイルに保存します。');
  console.log('');

  const browser = await launchBrowser();
  const context = await browser.newContext({ locale: 'ja-JP', viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  await page.goto('https://note.com/login', { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
  await ask('ログインできたら Enter … ');

  try {
    await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch {
    /* 失敗しても Cookie は取れることが多い */
  }

  // 開いたタブで取得した note 関連 Cookie をまとめる（手で DevTools を開かない）
  const list = (await context.cookies()).filter(
    (c) => /note\.com$/i.test(c.domain.replace(/^\./, '')) || c.domain === 'note.com'
  );
  const header = cookiesToHeader(list);

  if (!header || !header.includes('note_session')) {
    console.log('');
    console.log('⚠️  note_session が見つかりません。ログインできていない可能性があります。');
    console.log('   それでも保存しますか？ (y/N)');
    const ok = await ask('');
    if (String(ok).trim().toLowerCase() !== 'y') {
      await browser.close();
      process.exit(1);
    }
  }

  writeFileSync(outFile, header, 'utf-8');

  await browser.close();

  console.log('');
  console.log('✅ 保存しました:', outFile);
  console.log('');
  console.log('--- 次にやること（コピーは1回だけ）---');
  console.log('1. 上のファイルを開く（中身は1行の Cookie）');
  console.log('2. GitHub → Settings → Secrets → NOTE_SESSION_COOKIE に貼り付け');
  console.log('3. Variables に USE_NOTE_API = true');
  console.log('');
  console.log('（先頭 60 文字のプレビュー）');
  console.log(header.slice(0, 60) + (header.length > 60 ? '…' : ''));
  console.log('');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
