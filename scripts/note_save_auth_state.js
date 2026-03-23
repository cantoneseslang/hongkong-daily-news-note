#!/usr/bin/env node
/**
 * ローカルで note にログインしたあと、Playwright の storageState を保存する。
 * 出力ファイルの中身を GitHub Secret「NOTE_AUTH_STATE」にそのまま貼り付ける。
 *
 * 前提: リポジトリ直下で npm install
 * ブラウザ: まず「普段の Google Chrome」で起動（note が Playwright の Chromium を弾く場合があるため）。
 *   どうしても Chromium のみにしたいとき: NOTE_AUTH_FORCE_CHROMIUM=1 npm run note:auth
 *
 * 使い方:
 *   npm run note:auth
 *   または
 *   node scripts/note_save_auth_state.js [出力パス]
 *
 * デフォルト出力: ./.note-auth-state.json
 */

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import * as readline from 'readline';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

/**
 * 本物の Chrome / Edge を優先（note が同梱 Chromium をボット扱いしやすいため）
 */
/** Playwright 起動 Chrome が「自動操作」と判定されにくいよう緩和（完全ではない） */
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
    // 自動テスト用フラグを外す（検出されにくくする）
    ignoreDefaultArgs: ['--enable-automation'],
  };
  const forceChromium = process.env.NOTE_AUTH_FORCE_CHROMIUM === '1';

  if (!forceChromium) {
    try {
      console.log('ブラウザ: Google Chrome（検出緩和オプション付き）');
      return await chromium.launch({
        ...launchOpts,
        channel: 'chrome',
      });
    } catch (e) {
      console.log('⚠️  Google Chrome を起動できません:', e.message);
    }
    try {
      console.log('ブラウザ: Microsoft Edge を試します...');
      return await chromium.launch({
        ...launchOpts,
        channel: 'msedge',
      });
    } catch (e) {
      console.log('⚠️  Microsoft Edge を起動できません:', e.message);
    }
  }

  console.log('ブラウザ: Playwright 同梱 Chromium（NOTE_AUTH_FORCE_CHROMIUM=1 または Chrome/Edge なし）');
  console.log('   ※ note で「Could not log you in」のときは npm run note:auth:cdp を試してください。');
  return await chromium.launch({
    headless: false,
    args: [...STEALTH_CHROME_ARGS],
  });
}

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
  console.log('=== NOTE_AUTH_STATE 取得（ローカル）===');
  console.log('');
  console.log('1. これからブラウザが開きます。');
  console.log('2. note でログインしてください（SMS/アプリの二段階もここで入力できます）。');
  console.log('3. 可能なら https://editor.note.com/new まで進み、記事エディタが表示された状態にしてください。');
  console.log('4. 準備ができたら、このターミナルに戻り Enter を押します。');
  console.log('');
  console.log(`保存先: ${outPath}`);
  console.log('');

  const browser = await launchBrowser();

  const context = await browser.newContext({
    locale: 'ja-JP',
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  try {
    await page.goto('https://note.com/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
  } catch (e) {
    console.error('ページを開けませんでした:', e.message);
    await browser.close();
    process.exit(1);
  }

  await ask('ログインとエディタ表示まで完了したら Enter を押してください... ');

  let url = page.url();
  console.log(`現在のURL: ${url}`);

  if (url.includes('/login')) {
    console.log('');
    console.log('⚠️  まだログインページのURLです。editor に移動を試みます...');
    try {
      await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(2000);
      url = page.url();
      console.log(`移動後のURL: ${url}`);
    } catch (e) {
      console.error('editor への移動に失敗:', e.message);
    }
  }

  if (url.includes('/login')) {
    console.log('');
    console.log('⚠️  ログインできていない可能性があります。このまま保存すると Actions では使えません。');
    const ok = await ask('それでも保存しますか？ (y/N): ');
    if (String(ok).trim().toLowerCase() !== 'y') {
      console.log('中止しました。ブラウザを閉じます。');
      await browser.close();
      process.exit(1);
    }
  }

  const storageState = await context.storageState();
  const pretty = JSON.stringify(storageState, null, 2);
  const oneLine = JSON.stringify(storageState);

  writeFileSync(outPath, pretty, 'utf-8');
  const compactPath = outPath.replace(/\.json$/i, '') + '.compact.json';
  writeFileSync(compactPath, oneLine, 'utf-8');

  await browser.close();

  console.log('');
  console.log('✅ 保存しました:');
  console.log(`   整形版（読みやすい）: ${outPath}`);
  console.log(`   1行版（Secret に貼りやすい）: ${compactPath}`);
  console.log('');
  console.log('--- GitHub に反映する手順 ---');
  console.log('1. GitHub リポジトリ → Settings → Secrets and variables → Actions');
  console.log('2. NOTE_AUTH_STATE を「Update」し、次のいずれかを貼り付け:');
  console.log('   - .compact.json の中身（1行）を推奨');
  console.log('   - または .note-auth-state.json の中身（複数行でも可）');
  console.log('3. 保存後、Actions を手動実行するか、翌日の定時実行で確認。');
  console.log('');
  console.log('（確認）1行版の先頭 80 文字:');
  console.log(oneLine.slice(0, 80) + (oneLine.length > 80 ? '...' : ''));
  console.log('');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
