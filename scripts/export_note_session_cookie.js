#!/usr/bin/env node
/**
 * ブラウザをこちらで開く → あなたは note にログインするだけ → Cookie は自動でファイルに保存。
 * DevTools でコピーする必要はありません。
 *
 *   npm run note:cookie
 *
 * 環境変数（任意）:
 *   NOTE_COOKIE_USE_GOOGLE_CHROME=1  … 最初から Google Chrome で開く（同梱 Chromium より先）
 *   NOTE_COOKIE_PROFILE_DIR=パス     … プロファイル保存先を上書き（複数アカウント用）
 *   NOTE_COOKIE_NON_PERSISTENT=1     … 旧来どおり一時プロファイル（トラブル時のみ）
 *
 * 出力: .note-session-cookie.txt（GitHub Secret NOTE_SESSION_COOKIE にそのまま貼れる1行）
 *
 * ログイン方法: メールで通らない場合は X（𝕏）/ Google 等のソーシャルでも可（セッション Cookie さえ取れればよい）。
 */

import { chromium } from 'playwright';
import { writeFileSync, existsSync, mkdirSync } from 'fs';
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

const commonContextOpts = {
  headless: false,
  args: [...STEALTH_CHROME_ARGS],
  ignoreDefaultArgs: ['--enable-automation'],
  locale: 'ja-JP',
  viewport: { width: 1280, height: 800 },
};

function defaultProfileDir(kind) {
  const base =
    process.env.NOTE_COOKIE_PROFILE_DIR ||
    path.join(repoRoot, kind === 'chrome' ? '.note-cookie-profile-chrome' : '.note-cookie-profile');
  if (!existsSync(base)) {
    try {
      mkdirSync(base, { recursive: true });
    } catch {
      /* ignore */
    }
  }
  return base;
}

/**
 * 永続プロファイル付きコンテキスト（ログイン状態が次回に残りやすい／note の判定が緩むことがある）
 */
async function launchPersistent(kind) {
  const userDataDir = defaultProfileDir(kind);
  const opts =
    kind === 'chrome'
      ? { ...commonContextOpts, channel: 'chrome' }
      : { ...commonContextOpts };
  return chromium.launchPersistentContext(userDataDir, opts);
}

/** 旧: 毎回クリーンなブラウザ（互換・トラブル時） */
async function launchEphemeral() {
  const launchOpts = {
    headless: false,
    args: [...STEALTH_CHROME_ARGS],
    ignoreDefaultArgs: ['--enable-automation'],
  };
  if (process.env.NOTE_AUTH_FORCE_CHROMIUM === '1') {
    const browser = await chromium.launch({ headless: false, args: [...STEALTH_CHROME_ARGS] });
    return { browser, ephemeral: true };
  }
  if (process.env.NOTE_COOKIE_USE_GOOGLE_CHROME === '1') {
    try {
      console.log('→ Google Chrome（一時プロファイル）…');
      const browser = await chromium.launch({ ...launchOpts, channel: 'chrome' });
      return { browser, ephemeral: true };
    } catch (e) {
      console.log('⚠️ Chrome:', e.message);
    }
  }
  try {
    console.log('→ Playwright 同梱 Chromium（一時プロファイル）…');
    const browser = await chromium.launch({ headless: false, args: [...STEALTH_CHROME_ARGS] });
    return { browser, ephemeral: true };
  } catch (e) {
    console.log('⚠️ Chromium:', e.message);
  }
  try {
    const browser = await chromium.launch({ ...launchOpts, channel: 'chrome' });
    return { browser, ephemeral: true };
  } catch (e) {
    console.log('⚠️ Chrome:', e.message);
  }
  try {
    const browser = await chromium.launch({ ...launchOpts, channel: 'msedge' });
    return { browser, ephemeral: true };
  } catch (e) {
    console.log('⚠️ Edge:', e.message);
  }
  const browser = await chromium.launch({ headless: false, args: [...STEALTH_CHROME_ARGS] });
  return { browser, ephemeral: true };
}

async function openNoteSession() {
  if (process.env.NOTE_COOKIE_NON_PERSISTENT === '1') {
    const { browser, ephemeral } = await launchEphemeral();
    const context = await browser.newContext({ locale: 'ja-JP', viewport: { width: 1280, height: 800 } });
    return { context, close: async () => { await context.close(); await browser.close(); } };
  }

  const chromeFirst = process.env.NOTE_COOKIE_USE_GOOGLE_CHROME === '1';

  if (chromeFirst) {
    try {
      console.log('→ Google Chrome（永続プロファイル: .note-cookie-profile-chrome）…');
      const context = await launchPersistent('chrome');
      return { context, close: () => context.close() };
    } catch (e) {
      console.log('⚠️ Chrome 永続:', e.message);
    }
    try {
      console.log('→ Playwright 同梱 Chromium（永続プロファイル: .note-cookie-profile）…');
      const context = await launchPersistent('chromium');
      return { context, close: () => context.close() };
    } catch (e) {
      console.log('⚠️ Chromium 永続:', e.message);
    }
  } else {
    try {
      console.log('→ Playwright 同梱 Chromium（永続プロファイル: .note-cookie-profile）…');
      console.log('   （Chrome が落ちる場合は NOTE_COOKIE_USE_GOOGLE_CHROME=1 か、下の「手動」参照）');
      const context = await launchPersistent('chromium');
      return { context, close: () => context.close() };
    } catch (e) {
      console.log('⚠️ Chromium 永続:', e.message);
    }
    try {
      console.log('→ Google Chrome（永続プロファイル: .note-cookie-profile-chrome）…');
      const context = await launchPersistent('chrome');
      return { context, close: () => context.close() };
    } catch (e) {
      console.log('⚠️ Chrome 永続:', e.message);
    }
  }

  console.log('⚠️ 永続プロファイルで起動できませんでした。一時プロファイルにフォールバックします…');
  const { browser, ephemeral } = await launchEphemeral();
  const context = await browser.newContext({ locale: 'ja-JP', viewport: { width: 1280, height: 800 } });
  return { context, close: async () => { await context.close(); await browser.close(); } };
}

function ask(q) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(q, (a) => { rl.close(); resolve(a); }));
}

/** Playwright の cookie 配列を Cookie: ヘッダ用の1行にする */
function cookiesToHeader(cookies) {
  return cookies.map((c) => `${c.name}=${c.value}`).join('; ');
}

function printManualFallback() {
  console.log('');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('■ このウィンドウで note に入れないとき（最終手段）');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('1. ふだん使っている「普通の Google Chrome」だけで note.com にログインする');
  console.log('2. その Chrome を次で起動（ターミナルにコピペ）:');
  console.log('');
  console.log(
    '   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\\n' +
      '     --remote-debugging-port=9222 \\\n' +
      '     --user-data-dir="$HOME/chrome-note-debug"'
  );
  console.log('');
  console.log('3. 別ターミナルで:  npm run note:auth:cdp   （接続して storage / cookie を保存）');
  console.log('   または DevTools → Application → Cookies → note.com → 行を右クリックでコピー');
  console.log('4. `note_session=...` を含む行を GitHub Secret NOTE_SESSION_COOKIE に貼る');
  console.log('');
}

async function main() {
  const outFile = path.resolve(process.argv[2] || path.join(repoRoot, '.note-session-cookie.txt'));

  console.log('');
  console.log('=== NOTE_SESSION_COOKIE 自動取得 ===');
  console.log('');
  console.log('これからブラウザを開きます。');
  console.log('あなたがやること: 表示されたウィンドウで note にログイン（メールで通らなければ X(𝕏)/Google 等でも可。二段階もここで）。');
  console.log('できれば https://editor.note.com/new まで開いてください。');
  console.log('終わったらこのターミナルで Enter を押してください → Cookie は自動でファイルに保存します。');
  console.log('');

  const { context, close } = await openNoteSession();
  const pages = context.pages();
  const page = pages.length > 0 ? pages[0] : await context.newPage();

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
    printManualFallback();
    console.log('   それでも保存しますか？ (y/N)');
    const ok = await ask('');
    if (String(ok).trim().toLowerCase() !== 'y') {
      await close();
      process.exit(1);
    }
  }

  writeFileSync(outFile, header, 'utf-8');

  await close();

  console.log('');
  console.log('✅ 保存しました:', outFile);
  console.log('');
  console.log('--- 次にやること（コピーは1回だけ）---');
  console.log('1. 上のファイルを開く（中身は1行の Cookie）');
  console.log('2. GitHub → Settings → Secrets → NOTE_SESSION_COOKIE に貼り付け');
  console.log('');
  console.log('（先頭 60 文字のプレビュー）');
  console.log(header.slice(0, 60) + (header.length > 60 ? '…' : ''));
  console.log('');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
