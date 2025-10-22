#!/usr/bin/env node
/**
 * GitHub Actions用 note.com 自動投稿スクリプト
 * Puppeteerを使用してヘッドレスブラウザで投稿
 */

const fs = require('fs');
const path = require('path');

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
  console.log('Note.com 自動投稿スクリプト (GitHub Actions)');
  console.log('==================================================\n');

  // 1. Puppeteerをインポート
  const puppeteer = await import('puppeteer');
  
  // 2. Markdownファイルを読み込み
  const markdown = fs.readFileSync(markdownPath, 'utf-8');
  const { title, body } = parseMarkdown(markdown);
  
  console.log(`📝 記事情報:`);
  console.log(`   タイトル: ${title}`);
  console.log(`   本文: ${body.length}文字\n`);

  // 3. Puppeteer起動
  const browser = await puppeteer.default.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-web-security'
    ]
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    
    // User-Agentを設定
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    // 4. editor.note.com/new に直接アクセス（リダイレクトでログインページへ）
    console.log('🌐 note.com編集ページへアクセス中...');
    await page.goto('https://editor.note.com/new', { 
      waitUntil: 'networkidle0', 
      timeout: 60000 
    });
    
    await new Promise(resolve => setTimeout(resolve, 3000));
    const currentUrl = page.url();
    console.log(`現在のURL: ${currentUrl}`);
    
    // ログインページにリダイレクトされた場合
    if (currentUrl.includes('login') || currentUrl.includes('signin')) {
      console.log('🔐 ログインページが表示されました。ログイン処理を開始...');
      
      await page.screenshot({ path: '/tmp/login_page.png' });
      console.log('📷 ログインページのスクリーンショット: /tmp/login_page.png');
      
      // ページのHTMLを確認
      const bodyHTML = await page.content();
      const hasEmailField = bodyHTML.includes('type="email"') || bodyHTML.includes('email');
      const hasPasswordField = bodyHTML.includes('type="password"') || bodyHTML.includes('password');
      
      console.log(`📋 ページ構造確認:`);
      console.log(`   - メールフィールド検出: ${hasEmailField}`);
      console.log(`   - パスワードフィールド検出: ${hasPasswordField}`);
      
      // 全ての入力フィールドを探す
      const inputs = await page.$$('input');
      console.log(`   - 入力フィールド数: ${inputs.length}`);
      
      // 各入力フィールドの属性を確認
      for (let i = 0; i < Math.min(inputs.length, 5); i++) {
        const type = await inputs[i].evaluate(el => el.type);
        const name = await inputs[i].evaluate(el => el.name);
        const placeholder = await inputs[i].evaluate(el => el.placeholder);
        console.log(`   Input ${i+1}: type="${type}", name="${name}", placeholder="${placeholder}"`);
      }
      
      // メールアドレス入力（複数のパターンを試す）
      let emailEntered = false;
      const emailPatterns = [
        async () => {
          const input = await page.$('input[type="email"]');
          if (input) {
            await input.type(email);
            return true;
          }
          return false;
        },
        async () => {
          const input = await page.$('input[name*="email"]');
          if (input) {
            await input.type(email);
            return true;
          }
          return false;
        },
        async () => {
          const inputs = await page.$$('input[type="text"]');
          if (inputs.length > 0) {
            await inputs[0].type(email);
            return true;
          }
          return false;
        }
      ];
      
      for (const pattern of emailPatterns) {
        if (await pattern()) {
          emailEntered = true;
          console.log('✅ メールアドレス入力成功');
          break;
        }
      }
      
      if (!emailEntered) {
        throw new Error('メール入力欄が見つかりません');
      }
      
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // パスワード入力
      const passwordInput = await page.$('input[type="password"]');
      if (!passwordInput) {
        throw new Error('パスワード入力欄が見つかりません');
      }
      
      await passwordInput.type(password);
      console.log('✅ パスワード入力成功');
      
      await page.screenshot({ path: '/tmp/filled_form.png' });
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // ログインボタンをクリック
      const buttons = await page.$$('button');
      console.log(`📋 ボタン数: ${buttons.length}`);
      
      let loginButton = await page.$('button[type="submit"]');
      if (!loginButton) {
        // submitボタンがない場合、最初のボタンを使用
        loginButton = buttons[0];
      }
      
      if (!loginButton) {
        throw new Error('ログインボタンが見つかりません');
      }
      
      console.log('🔘 ログインボタンをクリック...');
      await Promise.all([
        loginButton.click(),
        page.waitForNavigation({ timeout: 30000 }).catch(() => console.log('⚠️  ナビゲーション待機タイムアウト'))
      ]);
      
      await new Promise(resolve => setTimeout(resolve, 3000));
      console.log(`ログイン後のURL: ${page.url()}`);
      
      // 再度編集ページへ移動
      if (!page.url().includes('editor.note.com')) {
        console.log('📝 編集ページへ再移動...');
        await page.goto('https://editor.note.com/new', { 
          waitUntil: 'networkidle0', 
          timeout: 30000 
        });
        await new Promise(resolve => setTimeout(resolve, 3000));
      }
    }
    
    console.log('✅ 編集ページへのアクセス成功');
    console.log(`現在のURL: ${page.url()}`);
    
    await page.screenshot({ path: '/tmp/editor_page.png' });
    console.log('📷 編集ページのスクリーンショット: /tmp/editor_page.png');

    // 5. タイトル入力
    console.log('📋 タイトル入力中...');
    
    // タイトル入力欄を探す（複数パターン）
    let titleInput = await page.$('textarea[placeholder*="タイトル"]');
    if (!titleInput) {
      titleInput = await page.$('input[placeholder*="タイトル"]');
    }
    if (!titleInput) {
      const textareas = await page.$$('textarea');
      titleInput = textareas[0];
    }
    
    if (!titleInput) {
      throw new Error('タイトル入力欄が見つかりません');
    }
    
    await titleInput.click();
    await titleInput.type(title, { delay: 10 });
    console.log('✅ タイトル入力完了');
    
    await page.waitForTimeout(1000);

    // 6. 本文入力
    console.log('📝 本文入力中...');
    
    // 本文入力欄を探す
    let bodyEditor = await page.$('.editor');
    if (!bodyEditor) {
      bodyEditor = await page.$('[contenteditable="true"]');
    }
    if (!bodyEditor) {
      const textareas = await page.$$('textarea');
      bodyEditor = textareas.length > 1 ? textareas[1] : null;
    }
    
    if (!bodyEditor) {
      throw new Error('本文入力欄が見つかりません');
    }
    
    await bodyEditor.click();
        await new Promise(resolve => setTimeout(resolve, 500));
    
    // 本文を小分けにして入力
    const chunkSize = 3000;
    for (let i = 0; i < body.length; i += chunkSize) {
      const chunk = body.substring(i, Math.min(i + chunkSize, body.length));
      await page.keyboard.type(chunk, { delay: 0 });
      console.log(`   入力進捗: ${Math.min(i + chunkSize, body.length)}/${body.length}文字`);
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    console.log('✅ 本文入力完了');
    
    await new Promise(resolve => setTimeout(resolve, 2000));

    // 7. 下書き保存
    console.log('💾 下書き保存中...');
    
    // 下書き保存ボタンを探す
    const saveButtonText = ['下書き保存', '保存', 'Save'];
    let saveButton = null;
    
    for (const text of saveButtonText) {
      const buttons = await page.$$('button');
      for (const button of buttons) {
        const buttonText = await button.evaluate(el => el.textContent);
        if (buttonText && buttonText.includes(text)) {
          saveButton = button;
          console.log(`✅ 保存ボタンを発見: "${buttonText}"`);
          break;
        }
      }
      if (saveButton) break;
    }
    
    if (saveButton) {
      await saveButton.click();
      await new Promise(resolve => setTimeout(resolve, 3000));
      console.log('✅ 下書き保存完了！');
    } else {
      console.log('⚠️  下書き保存ボタンが見つかりませんでした');
    }

    // 8. 最終URLを取得
    const finalUrl = page.url();
    console.log(`🔗 記事URL: ${finalUrl}\n`);
    
    await page.screenshot({ path: '/tmp/final_page.png' });
    console.log('📷 最終ページのスクリーンショット: /tmp/final_page.png');

    console.log('\n==================================================');
    console.log('✅ note.com投稿完了！');
    console.log('==================================================\n');

    return finalUrl;

  } catch (error) {
    console.error('\n❌ エラー発生:', error.message);
    console.error('スタックトレース:', error.stack);
    
    // エラー時のスクリーンショットとHTMLを保存
    try {
      const page = browser.pages()[0] || await browser.newPage();
      await page.screenshot({ path: '/tmp/error_screenshot.png', fullPage: true });
      const html = await page.content();
      fs.writeFileSync('/tmp/error_page.html', html);
      console.log('📷 エラースクリーンショット: /tmp/error_screenshot.png');
      console.log('📄 エラー時のHTML: /tmp/error_page.html');
      console.log(`🔗 現在のURL: ${page.url()}`);
    } catch (e) {
      console.log('⚠️  エラー情報の保存失敗');
    }
    
    throw error;
  } finally {
    await browser.close();
  }
}

async function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 3) {
    console.error('使用方法: node post_to_note_github_actions.js <markdown_file> <email> <password>');
    process.exit(1);
  }

  const [markdownPath, email, password] = args;

  try {
    await postToNote(markdownPath, email, password);
    console.log('✅ 処理完了');
    process.exit(0);
  } catch (error) {
    console.error('❌ 処理失敗:', error.message);
    process.exit(1);
  }
}

main();
