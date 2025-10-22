#!/usr/bin/env node
/**
 * GitHub Actions用 note.com 自動投稿スクリプト
 * Playwrightを使用（既存のnote-post-mcpと同じ技術）
 */

import { chromium } from 'playwright';
import { readFileSync } from 'fs';

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

async function postToNote(markdownPath, email, password) {
  console.log('\n==================================================');
  console.log('Note.com 自動投稿 (Playwright)');
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

    // editor.note.com/new に直接アクセス
    console.log('🌐 editor.note.com/new に移動中...');
    await page.goto('https://editor.note.com/new', { waitUntil: 'networkidle', timeout: 60000 });
    
    const currentUrl = page.url();
    console.log(`現在のURL: ${currentUrl}`);

    // ログインページにリダイレクトされた場合
    if (currentUrl.includes('login')) {
      console.log('🔐 ログインが必要です...');
      
      await page.waitForTimeout(2000);
      await page.screenshot({ path: '/tmp/login_page.png' });
      
      // 「メールアドレスでログイン」ボタンをクリック
      const emailButton = page.locator('text=メールアドレスでログイン').first();
      if (await emailButton.isVisible()) {
        console.log('📧 メールアドレスでログインボタンをクリック...');
        await emailButton.click();
        await page.waitForTimeout(1000);
      }
      
      // メールアドレス入力（placeholderで検索）
      console.log('ID入力欄を探しています...');
      const emailInput = await page.locator('input[placeholder*="note ID"], input[placeholder*="mail"], input[type="email"]').first();
      await emailInput.waitFor({ state: 'visible', timeout: 10000 });
      await emailInput.click();
      await page.waitForTimeout(500);
      await emailInput.type(email, { delay: 100 });
      console.log('✅ メール入力完了');
      
      await page.waitForTimeout(1000);
      
      // パスワード入力
      console.log('パスワード入力欄を探しています...');
      const passwordInput = await page.locator('input[type="password"]').first();
      await passwordInput.waitFor({ state: 'visible', timeout: 10000 });
      await passwordInput.click();
      await page.waitForTimeout(500);
      await passwordInput.type(password, { delay: 100 });
      console.log('✅ パスワード入力完了');
      
      await page.waitForTimeout(1000);
      
      // ログインボタンをクリック
      console.log('ログインボタンを探しています...');
      const loginButton = await page.locator('button[type="submit"], button:has-text("ログイン")').first();
      await loginButton.waitFor({ state: 'visible', timeout: 10000 });
      await loginButton.click();
      console.log('✓ ログインボタンをクリック');
      
      // ログイン完了を待機
      await page.waitForTimeout(5000);
      
      console.log('✅ ログイン成功');
      console.log(`ログイン後URL: ${page.url()}`);
      
      // editor.note.com/new に再度移動
      if (!page.url().includes('editor.note.com')) {
        console.log('🌐 editor.note.com/new に再度移動中...');
        await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded' });
      }
    }
    
    // 編集ページの完全な読み込みを待つ
    console.log('📄 編集ページの読み込み待機中...');
    await page.waitForLoadState('networkidle', { timeout: 30000 });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/tmp/editor_page.png' });
    console.log(`📷 編集ページのスクリーンショット保存`);
    console.log(`現在のURL: ${page.url()}`);

    // タイトル入力
    console.log('📋 タイトル入力中...');
    await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 30000 });
    await page.fill('textarea[placeholder*="タイトル"]', title);
    console.log('✅ タイトル入力完了');

    // 本文入力
    console.log('📝 本文入力中...');
    const bodyBox = page.locator('div[contenteditable="true"][role="textbox"]').first();
    await bodyBox.waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(2000);
    await bodyBox.click({ force: true });
    await page.keyboard.type(body);
    console.log('✅ 本文入力完了');

    // 下書き保存
    console.log('💾 下書き保存中...');
    await page.waitForTimeout(2000);
    
    const saveButton = await page.locator('button:has-text("下書き")').first();
    if (await saveButton.count() > 0) {
      await saveButton.click();
      await page.waitForTimeout(3000);
      console.log('✅ 下書き保存完了！');
    }

    const finalUrl = page.url();
    console.log(`🔗 記事URL: ${finalUrl}\n`);
    
    await page.screenshot({ path: '/tmp/final_page.png' });

    console.log('\n==================================================');
    console.log('✅ note.com投稿成功！');
    console.log('==================================================\n');

    return finalUrl;

  } catch (error) {
    console.error('\n❌ エラー発生:', error.message);
    
    try {
      const pages = context.pages();
      if (pages.length > 0) {
        await pages[0].screenshot({ path: '/tmp/error_screenshot.png', fullPage: true });
        const html = await pages[0].content();
        require('fs').writeFileSync('/tmp/error_page.html', html);
        console.log('📷 エラースクリーンショット: /tmp/error_screenshot.png');
        console.log(`🔗 現在のURL: ${pages[0].url()}`);
      }
    } catch (e) {
      // デバッグ情報保存失敗は無視
    }
    
    throw error;
  } finally {
    await browser.close();
  }
}

const [, , markdownPath, email, password] = process.argv;

if (!markdownPath || !email || !password) {
  console.error('使用方法: node post_to_note_playwright.js <markdown_file> <email> <password>');
  process.exit(1);
}

postToNote(markdownPath, email, password)
  .then(() => process.exit(0))
  .catch((error) => {
    console.error('❌ 処理失敗:', error.message);
    process.exit(1);
  });

