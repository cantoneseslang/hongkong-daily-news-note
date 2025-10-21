#!/usr/bin/env node
/**
 * GitHub Actions用 note.com 自動投稿スクリプト
 * Puppeteerを使用してヘッドレスブラウザで投稿
 */

const fs = require('fs');
const path = require('path');

async function postToNote(markdownPath, email, password) {
  console.log('\n==================================================');
  console.log('Note.com 自動投稿スクリプト (GitHub Actions)');
  console.log('==================================================\n');

  // 1. Puppeteerをインポート（動的インポート）
  const puppeteer = await import('puppeteer');
  
  // 2. Markdownファイルを読み込み
  const markdown = fs.readFileSync(markdownPath, 'utf-8');
  
  // タイトル・本文・タグを抽出
  const titleMatch = markdown.match(/^# (.+)$/m);
  const title = titleMatch ? titleMatch[1] : 'タイトル未設定';
  
  // 天気情報以降を本文として抽出
  const bodyStartIndex = markdown.indexOf('## 本日の香港の天気');
  const bodyEndIndex = markdown.lastIndexOf('**タグ**:');
  const body = bodyStartIndex !== -1 && bodyEndIndex !== -1 
    ? markdown.substring(bodyStartIndex, bodyEndIndex).trim()
    : markdown.substring(markdown.indexOf('\n') + 1).trim();
  
  console.log(`📝 記事情報:`);
  console.log(`   タイトル: ${title}`);
  console.log(`   本文: ${body.length}文字`);
  console.log('');

  // 3. Puppeteer起動
  const browser = await puppeteer.default.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu'
    ]
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    // 4. note.comログイン
    console.log('🔐 note.comにログイン中...');
    await page.goto('https://note.com/login', { waitUntil: 'networkidle2', timeout: 60000 });
    
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
    await page.type('input[type="email"]', email);
    await page.type('input[type="password"]', password);
    
    // ログインボタンをクリック
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 })
    ]);
    
    console.log('✅ ログイン成功');

    // 5. 新規記事作成ページへ移動
    console.log('📄 新規記事作成ページへ移動中...');
    await page.goto('https://note.com/creator', { waitUntil: 'networkidle2', timeout: 30000 });
    
    // 「記事を書く」ボタンをクリック
    await page.waitForSelector('a[href*="/notes/new"]', { timeout: 10000 });
    await page.click('a[href*="/notes/new"]');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 });

    console.log('✅ 記事作成ページ表示');

    // 6. タイトル入力
    console.log('📋 タイトル入力中...');
    await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 10000 });
    await page.click('textarea[placeholder*="タイトル"]');
    await page.type('textarea[placeholder*="タイトル"]', title);
    console.log('✅ タイトル入力完了');

    // 7. 本文入力
    console.log('📝 本文入力中...');
    await page.waitForSelector('.editor', { timeout: 10000 });
    await page.click('.editor');
    
    // 本文を小分けにして入力（タイムアウト防止）
    const chunkSize = 5000;
    for (let i = 0; i < body.length; i += chunkSize) {
      const chunk = body.substring(i, Math.min(i + chunkSize, body.length));
      await page.keyboard.type(chunk, { delay: 0 });
      console.log(`   入力進捗: ${Math.min(i + chunkSize, body.length)}/${body.length}文字`);
    }
    console.log('✅ 本文入力完了');

    // 8. タグ入力
    console.log('🏷️  タグ入力中...');
    // タグボタンを探してクリック
    await page.waitForSelector('button[aria-label*="タグ"], button:has-text("タグ")', { timeout: 5000 }).catch(() => {
      console.log('⚠️  タグボタンが見つかりません。スキップします。');
    });
    
    try {
      const tagButton = await page.$('button[aria-label*="タグ"], button:has-text("タグ")');
      if (tagButton) {
        await tagButton.click();
        await page.waitForTimeout(1000);
        
        // タグを入力
        const tags = ['今日の広東語', '広東語'];
        for (const tag of tags) {
          await page.keyboard.type(tag);
          await page.keyboard.press('Enter');
          await page.waitForTimeout(500);
        }
        console.log(`✅ タグ入力完了: ${tags.join(', ')}`);
      }
    } catch (e) {
      console.log('⚠️  タグ入力をスキップしました');
    }

    // 9. 下書き保存
    console.log('💾 下書き保存中...');
    await page.waitForTimeout(2000);
    
    // 下書き保存ボタンをクリック
    const saveButton = await page.$('button:has-text("下書き保存")');
    if (saveButton) {
      await saveButton.click();
      await page.waitForTimeout(3000);
      console.log('✅ 下書き保存完了！');
    } else {
      console.log('⚠️  下書き保存ボタンが見つかりません。手動で保存してください。');
    }

    // 10. 現在のURLを取得
    const currentUrl = page.url();
    console.log(`🔗 記事URL: ${currentUrl}\n`);

    console.log('==================================================');
    console.log('✅ note.com投稿完了！');
    console.log('==================================================\n');

    return currentUrl;

  } catch (error) {
    console.error('❌ エラー発生:', error.message);
    
    // エラー時のスクリーンショットを保存
    try {
      await page.screenshot({ path: '/tmp/error_screenshot.png' });
      console.log('📷 エラースクリーンショット: /tmp/error_screenshot.png');
    } catch (e) {
      // スクリーンショット保存失敗は無視
    }
    
    throw error;
  } finally {
    await browser.close();
  }
}

// メイン実行
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.length < 3) {
    console.error('使用方法: node post_to_note_github_actions.js <markdown_file> <email> <password>');
    process.exit(1);
  }

  const [markdownPath, email, password] = args;

  postToNote(markdownPath, email, password)
    .then(() => {
      console.log('✅ 処理完了');
      process.exit(0);
    })
    .catch((error) => {
      console.error('❌ 処理失敗:', error.message);
      process.exit(1);
    });
}

module.exports = { postToNote };

