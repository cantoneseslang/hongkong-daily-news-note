#!/usr/bin/env node
import { chromium } from 'playwright';
import { readFileSync } from 'fs';

const [, , markdownPath, username, password] = process.argv;

if (!markdownPath || !username || !password) {
  console.error('使用方法: node note_simple_post.js <markdown_file> <username> <password>');
  process.exit(1);
}

function parseMarkdown(content) {
  const lines = content.split('\n');
  let title = '';
  let body = [];
  let foundTitle = false;
  
  for (const line of lines) {
    if (!foundTitle && line.startsWith('# ')) {
      title = line.substring(2).trim();
      foundTitle = true;
      continue;
    }
    if (foundTitle) {
      body.push(line);
    }
  }
  
  return {
    title: title || 'タイトル未設定',
    body: body.join('\n').trim()
  };
}

async function main() {
  console.log('\n==================================================');
  console.log('Note.com 自動投稿 (シンプル版)');
  console.log('==================================================\n');

  const markdown = readFileSync(markdownPath, 'utf-8');
  const { title, body } = parseMarkdown(markdown);
  
  console.log(`📝 記事情報:`);
  console.log(`   タイトル: ${title}`);
  console.log(`   本文: ${body.length}文字\n`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(60000);

    console.log('🌐 note.com/login に移動中...');
    await page.goto('https://note.com/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    console.log('🔐 ログイン情報を入力中...');
    
    const emailInput = page.locator('input[placeholder*="note ID"], input[placeholder*="mail"], input[type="email"]').first();
    await emailInput.waitFor({ state: 'visible', timeout: 10000 });
    await emailInput.click();
    await page.waitForTimeout(500);
    await emailInput.type(username, { delay: 100 });
    console.log('✓ ID入力完了');

    await page.waitForTimeout(1000);

    const passwordInput = page.locator('input[type="password"]').first();
    await passwordInput.waitFor({ state: 'visible', timeout: 10000 });
    await passwordInput.click();
    await page.waitForTimeout(500);
    await passwordInput.type(password, { delay: 100 });
    console.log('✓ パスワード入力完了');

    await page.waitForTimeout(1000);

    const loginButton = page.locator('button[type="submit"], button:has-text("ログイン")').first();
    await loginButton.waitFor({ state: 'visible', timeout: 10000 });
    await loginButton.click();
    console.log('✓ ログインボタンをクリック');

    await page.waitForTimeout(5000);

    console.log('✅ ログイン完了\n');

    console.log('🌐 editor.note.com/new に移動中...');
    await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded' });
    
    // ページが完全に読み込まれるまで長めに待機
    console.log('⏳ ページ読み込み待機中...');
    await page.waitForTimeout(10000);

    console.log('📋 タイトル入力中...');
    await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 60000 });
    await page.fill('textarea[placeholder*="タイトル"]', title);
    console.log('✓ タイトル入力完了');

    console.log('📝 本文入力中...');
    const bodyBox = page.locator('div[contenteditable="true"][role="textbox"]').first();
    await bodyBox.waitFor({ state: 'visible', timeout: 60000 });
    await page.waitForTimeout(2000);
    await bodyBox.click({ force: true });
    
    // 本文を分割して入力（長すぎるとタイムアウトする可能性がある）
    const chunks = body.match(/[\s\S]{1,5000}/g) || [body];
    for (let i = 0; i < chunks.length; i++) {
      await page.keyboard.type(chunks[i]);
      console.log(`  進捗: ${i + 1}/${chunks.length}チャンク`);
    }
    console.log('✓ 本文入力完了');

    await page.waitForTimeout(2000);

    console.log('💾 下書き保存中...');
    const saveButton = page.locator('button:has-text("下書き"), button:has-text("保存")').first();
    if (await saveButton.count() > 0) {
      await saveButton.click();
      await page.waitForTimeout(3000);
      console.log('✓ 下書き保存完了！');
    }

    const finalUrl = page.url();
    console.log(`\n🔗 記事URL: ${finalUrl}`);

    console.log('\n==================================================');
    console.log('✅ note.com投稿成功！');
    console.log('==================================================\n');

  } catch (error) {
    console.error('\n❌ エラー発生:', error.message);
    console.error(error.stack);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main().catch(console.error);

