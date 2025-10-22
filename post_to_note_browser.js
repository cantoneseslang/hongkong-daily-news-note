import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import * as path from 'path';
import * as os from 'os';

function parseMarkdown(content) {
  const lines = content.split('\n');
  let title = '';
  let body = '';
  const tags = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (!title && line.startsWith('# ')) {
      title = line.substring(2).trim();
      continue;
    }

    if (line.startsWith('**タグ**:')) {
      const tagsStr = line.substring('**タグ**:'.length).trim();
      tags.push(...tagsStr.split(',').map(t => t.trim()));
      continue;
    }

    if (line.startsWith('**生成日時**:')) {
      continue;
    }

    if (i > 0 && line !== '---') {
      body += line + '\n';
    }
  }

  return {
    title: title || 'Untitled',
    body: body.trim(),
    tags: tags.filter(Boolean),
  };
}

async function saveDraft(markdownPath, username, password, statePath) {
  console.log('='.repeat(50));
  console.log('香港ニュース note 自動投稿');
  console.log('='.repeat(50));

  const mdContent = readFileSync(markdownPath, 'utf-8');
  const { title, body, tags } = parseMarkdown(mdContent);

  console.log('\n📝 記事情報:');
  console.log(`タイトル: ${title}`);
  console.log(`タグ: ${tags.join(', ')}`);
  console.log(`本文: ${body.length}文字\n`);

  const browser = await chromium.launch({
    headless: false,
    args: ['--lang=ja-JP'],
  });

  try {
    let contextOptions = {
      locale: 'ja-JP',
    };
    
    if (existsSync(statePath)) {
      console.log(`✓ 保存済み認証状態を使用: ${statePath}`);
      contextOptions.storageState = statePath;
    } else {
      console.log('⚠ 認証状態なし - ログインが必要です');
    }
    
    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();
    page.setDefaultTimeout(30000);

    console.log('🌐 editor.note.com/new に移動中...');
    await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    const currentUrl = page.url();
    console.log(`現在のURL: ${currentUrl}`);

    if (currentUrl.includes('/login')) {
      console.log('\n🔐 ログインが必要です。自動ログイン中...');
      
      await page.waitForTimeout(2000);
      
      console.log('ID入力欄を探しています...');
      const emailInput = await page.locator('input[placeholder*="note ID"], input[placeholder*="mail"]').first();
      await emailInput.waitFor({ state: 'visible', timeout: 10000 });
      await emailInput.click();
      await page.waitForTimeout(500);
      await emailInput.type(username, { delay: 100 });
      console.log('✓ ID入力完了');
      await page.waitForTimeout(1000);

      console.log('パスワード入力欄を探しています...');
      const passwordInput = await page.locator('input[type="password"]').first();
      await passwordInput.waitFor({ state: 'visible', timeout: 10000 });
      await passwordInput.click();
      await page.waitForTimeout(500);
      await passwordInput.type(password, { delay: 100 });
      console.log('✓ パスワード入力完了');
      await page.waitForTimeout(1000);

      console.log('ログインボタンを探しています...');
      const loginButton = await page.locator('button[type="submit"], button:has-text("ログイン")').first();
      await loginButton.waitFor({ state: 'visible', timeout: 10000 });
      await loginButton.click();
      console.log('✓ ログインボタンをクリック');
      
      await page.waitForTimeout(5000);
      
      const storageState = await context.storageState();
      writeFileSync(statePath, JSON.stringify(storageState, null, 2));
      console.log(`✓ 認証状態を保存: ${statePath}\n`);

      console.log('🌐 editor.note.com/new に再度移動中...');
      await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
    }

    console.log('📋 タイトル入力中...');
    await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 10000 });
    await page.fill('textarea[placeholder*="タイトル"]', title);
    console.log('✓ タイトル入力完了');

    console.log('📝 本文入力中...');
    
    const bodyBox = page.locator('div[contenteditable="true"][role="textbox"]').first();
    await bodyBox.waitFor({ state: 'visible' });
    await page.waitForTimeout(2000);
    await bodyBox.click({ force: true });

    // 本文を一括入力
    await page.keyboard.type(body, { delay: 5 });
    console.log('✓ 本文入力完了');

    console.log('💾 下書き保存中...');
    const saveBtn = page.locator('button:has-text("下書き保存")').first();
    await saveBtn.waitFor({ state: 'visible' });
    
    for (let i = 0; i < 20; i++) {
      if (await saveBtn.isEnabled()) break;
      await page.waitForTimeout(100);
    }
    
    await saveBtn.click();
    await page.waitForTimeout(3000);

    console.log('✓ 下書き保存完了！');
    console.log(`🔗 URL: ${page.url()}\n`);

    const screenshotPath = path.join(os.tmpdir(), `note-draft-${Date.now()}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`📷 スクリーンショット: ${screenshotPath}\n`);

    console.log('='.repeat(50));
    console.log('✅ 処理が完了しました！');
    console.log('='.repeat(50));
    console.log('\n🔒 ブラウザを閉じています...\n');
    
    await page.waitForTimeout(2000);

  } catch (error) {
    console.error('\n❌ エラー発生:', error.message);
    try {
      const errorPath = path.join(os.tmpdir(), `error-${Date.now()}.png`);
      await page.screenshot({ path: errorPath, fullPage: true });
      console.log(`エラースクリーンショット: ${errorPath}`);
    } catch (screenshotError) {
      console.log('スクリーンショットの保存に失敗しました');
    }
  } finally {
    await browser.close();
  }
}

const markdownPath = process.argv[2] || 'daily-articles/hongkong-news_2025-10-16.md';
const username = process.argv[3] || 'bestinksalesman';
const password = process.argv[4] || 'Hsakon0419';
const statePath = process.argv[5] || '/Users/sakonhiroki/.note-state.json';

console.log(`📄 記事: ${markdownPath}\n`);

saveDraft(markdownPath, username, password, statePath).catch(console.error);

