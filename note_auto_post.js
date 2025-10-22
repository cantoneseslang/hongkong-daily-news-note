import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import * as path from 'path';
import * as os from 'os';

// URLファイルを読み込む（オプショナル）
function loadUrls() {
  const urlsPath = path.join(path.dirname(new URL(import.meta.url).pathname), 'images', 'urls.txt');
  
  // ファイルがなければ空のオブジェクトを返す
  if (!existsSync(urlsPath)) {
    return {};
  }
  
  const content = readFileSync(urlsPath, 'utf-8');
  const urls = {};
  
  content.split('\n').forEach(line => {
    if (line.startsWith('#') || !line.trim()) return;
    const [key, value] = line.split('=');
    if (key && value) {
      urls[key.trim()] = value.trim();
    }
  });
  
  return urls;
}

// 画像情報を抽出（画像+リンク結合形式も含む）
function extractImages(markdown, baseDir) {
  const images = [];
  
  // 通常の画像: ![alt](path)
  const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
  let match;
  
  while ((match = imageRegex.exec(markdown)) !== null) {
    const alt = match[1] || 'image';
    const imagePath = match[2];
    
    // URLではなくローカルパスの場合のみ処理
    if (!imagePath.startsWith('http://') && !imagePath.startsWith('https://')) {
      const absolutePath = path.resolve(baseDir, imagePath);
      if (existsSync(absolutePath)) {
        images.push({
          alt,
          localPath: imagePath,
          relativePath: imagePath,
          absolutePath,
          hasLink: false, // リンクなし
        });
      } else {
        console.log(`⚠ 画像ファイルが見つかりません: ${absolutePath}`);
      }
    }
  }
  
  // 画像+リンク結合: [![alt](path)](url)
  const linkedImageRegex = /\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)/g;
  while ((match = linkedImageRegex.exec(markdown)) !== null) {
    const alt = match[1] || 'image';
    const imagePath = match[2];
    const linkUrl = match[3];
    
    if (!imagePath.startsWith('http://') && !imagePath.startsWith('https://')) {
      const absolutePath = path.resolve(baseDir, imagePath);
      if (existsSync(absolutePath)) {
        images.push({
          alt,
          localPath: imagePath,
          relativePath: imagePath,
          absolutePath,
          hasLink: true,
          linkUrl,
        });
      } else {
        console.log(`⚠ 画像ファイルが見つかりません: ${absolutePath}`);
      }
    }
  }
  
  return images;
}

function parseMarkdown(content) {
  const lines = content.split('\n');
  let title = '';
  let body = '';
  const tags = [];
  let thumbnail = '';
  let inFrontMatter = false;
  let frontMatterEnded = false;
  let titleFound = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Front matterは最初の行が---で始まる場合のみ有効
    if (i === 0 && line.trim() === '---') {
      inFrontMatter = true;
      continue;
    }

    if (line.trim() === '---' && inFrontMatter && !frontMatterEnded) {
      inFrontMatter = false;
      frontMatterEnded = true;
      continue;
    }

    if (inFrontMatter) {
      if (line.startsWith('title:')) {
        title = line.substring(6).trim().replace(/^["']|["']$/g, '');
      } else if (line.startsWith('thumbnail:')) {
        thumbnail = line.substring(10).trim().replace(/^["']|["']$/g, '');
      } else if (line.startsWith('tags:')) {
        const tagsStr = line.substring(5).trim();
        if (tagsStr.startsWith('[') && tagsStr.endsWith(']')) {
          tags.push(...tagsStr.slice(1, -1).split(',').map(t => t.trim().replace(/^["']|["']$/g, '')));
        }
      } else if (line.trim().startsWith('-')) {
        const tag = line.trim().substring(1).trim().replace(/^["']|["']$/g, '');
        if (tag) tags.push(tag);
      }
      continue;
    }

    // タイトル行をスキップ
    if (!titleFound && line.startsWith('# ')) {
      if (!title) {
        title = line.substring(2).trim();
      }
      titleFound = true;
      continue;
    }

    // タイトルが見つかった後は全て本文に追加
    if (titleFound) {
      body += line + '\n';
    }
  }

  return {
    title: title || 'Untitled',
    body: body.trim(),
    tags: tags.filter(Boolean),
    thumbnail: thumbnail,
  };
}

async function saveDraft(markdownPath, username, password, statePath, isPublish = false) {
  console.log('='.repeat(50));
  console.log(isPublish ? 'Note 自動ログイン & 公開ツール' : 'Note 自動ログイン & 下書き保存ツール');
  console.log('='.repeat(50));

  const mdContent = readFileSync(markdownPath, 'utf-8');
  const { title, body, tags, thumbnail } = parseMarkdown(mdContent);
  
  // URLを読み込む
  const urls = loadUrls();
  console.log('✓ URLファイル読み込み完了');

  console.log('\n📝 記事情報:');
  console.log(`タイトル: ${title}`);
  console.log(`タグ: ${tags.join(', ')}`);
  if (thumbnail) {
    console.log(`見出し画像: ${thumbnail}`);
  }
  console.log(`本文: ${body.length}文字\n`);

  const browser = await chromium.launch({
    headless: false,
    args: ['--lang=ja-JP'],
  });

  try {
    // 認証状態ファイルがあれば読み込む
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

    // ログインページにリダイレクトされたかチェック
    const currentUrl = page.url();
    console.log(`現在のURL: ${currentUrl}`);

    if (currentUrl.includes('/login')) {
      console.log('\n🔐 ログインが必要です。自動ログイン中...');
      
      await page.waitForTimeout(2000);
      
      // メールアドレスまたはnoteIDを入力
      console.log('ID入力欄を探しています...');
      const emailInput = await page.locator('input[placeholder*="note ID"], input[placeholder*="mail"]').first();
      await emailInput.waitFor({ state: 'visible', timeout: 10000 });
      await emailInput.click();
      await page.waitForTimeout(500);
      await emailInput.type(username, { delay: 100 });
      console.log('✓ ID入力完了');
      await page.waitForTimeout(1000);

      // パスワードを入力
      console.log('パスワード入力欄を探しています...');
      const passwordInput = await page.locator('input[type="password"]').first();
      await passwordInput.waitFor({ state: 'visible', timeout: 10000 });
      await passwordInput.click();
      await page.waitForTimeout(500);
      await passwordInput.type(password, { delay: 100 });
      console.log('✓ パスワード入力完了');
      await page.waitForTimeout(1000);

      // ログインボタンをクリック
      console.log('ログインボタンを探しています...');
      const loginButton = await page.locator('button[type="submit"], button:has-text("ログイン")').first();
      await loginButton.waitFor({ state: 'visible', timeout: 10000 });
      await loginButton.click();
      console.log('✓ ログインボタンをクリック');
      
      // ログイン完了を待機
      await page.waitForTimeout(5000);
      
      // 認証状態を保存
      const storageState = await context.storageState();
      writeFileSync(statePath, JSON.stringify(storageState, null, 2));
      console.log(`✓ 認証状態を保存: ${statePath}\n`);

      // 新規記事作成ページに再度移動
      console.log('🌐 editor.note.com/new に再度移動中...');
      await page.goto('https://editor.note.com/new', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
    }

    console.log('📋 タイトル入力中...');
    await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 10000 });
    await page.fill('textarea[placeholder*="タイトル"]', title);
    console.log('✓ タイトル入力完了');

    // 見出し画像を設定（本文入力の前）
    if (thumbnail) {
      const thumbnailPath = path.resolve(path.dirname(markdownPath), thumbnail);
      
      if (existsSync(thumbnailPath)) {
        console.log('🖼️  見出し画像を設定中...');
        
        try {
          await page.waitForTimeout(2000);
          
          // 見出し画像ボタンを探してクリック
          const thumbnailButton = page.locator('button[aria-label="画像を追加"]').first();
          await thumbnailButton.waitFor({ state: 'visible', timeout: 5000 });
          await thumbnailButton.click();
          await page.waitForTimeout(1000);
          
          // 「画像をアップロード」ボタンをクリック
          const uploadButton = page.locator('button:has-text("画像をアップロード")').first();
          await uploadButton.waitFor({ state: 'visible', timeout: 5000 });
          await uploadButton.click();
          await page.waitForTimeout(1000);
          
          // ファイル入力要素を探してファイルを設定
          const fileInput = page.locator('input[type="file"]').first();
          await fileInput.setInputFiles(thumbnailPath);
          await page.waitForTimeout(2000);
          
          // アップロード完了を待つ
          await page.waitForTimeout(3000);
          
          // クロップモーダル内の保存ボタンをクリック
          console.log('クロップモーダル内の保存ボタンを待っています...');
          await page.waitForTimeout(3000);
          
          try {
            // クロップモーダル内の保存ボタンを探す
            const cropModalSaveButton = page.locator('.CropModal__overlay button:has-text("保存"), .ReactModal__Overlay button:has-text("保存")').last();
            await cropModalSaveButton.waitFor({ state: 'visible', timeout: 5000 });
            console.log('クロップモーダルの保存ボタンをクリックしています...');
            await cropModalSaveButton.click();
            await page.waitForTimeout(2000);
            console.log('✓ クロップモーダルの保存ボタンをクリックしました');
          } catch (e) {
            console.log('⚠️  保存ボタンが見つかりませんでした:', e.message);
          }
          
          // ファイル参照ウィンドウが開いていたらEscで閉じる
          console.log('ファイル参照ウィンドウを閉じています...');
          await page.waitForTimeout(1000);
          await page.keyboard.press('Escape');
          await page.waitForTimeout(1000);
          console.log('✓ ファイル参照ウィンドウを閉じました');
          
          console.log('✓ 見出し画像設定完了');
        } catch (error) {
          console.log('⚠️  見出し画像設定エラー:', error.message);
          console.log('見出し画像なしで続行します...');
        }
      }
    }

    console.log('📝 本文入力中...');
    
    // Canvaヘルプボタンが表示されていたら閉じる
    try {
      const canvaHelpButton = page.locator('button[aria-label*="Canva"]').first();
      if (await canvaHelpButton.isVisible({ timeout: 2000 })) {
        console.log('Canvaヘルプを閉じています...');
        await canvaHelpButton.click();
        await page.waitForTimeout(1000);
      }
    } catch (e) {
      // Canvaヘルプがない場合は無視
    }
    
    // 本文中の画像を抽出
    const images = extractImages(body, path.dirname(markdownPath));
    if (images.length > 0) {
      console.log(`📷 画像を ${images.length} 個検出しました`);
      images.forEach(img => {
        console.log(`  - ${img.alt}: ${img.relativePath}${img.hasLink ? ' (リンク付き)' : ''}`);
      });
    }
    
    const bodyBox = page.locator('div[contenteditable="true"][role="textbox"]').first();
    await bodyBox.waitFor({ state: 'visible' });
    
    // 要素が安定するまで待つ
    await page.waitForTimeout(2000);
    
    // 強制的にクリック
    await bodyBox.click({ force: true });

    const lines = body.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const isLastLine = i === lines.length - 1;

      // 画像+リンク結合マークダウンを検出: [![alt](path)](url)
      const linkedImageMatch = line.match(/\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)/);
      if (linkedImageMatch) {
        const alt = linkedImageMatch[1];
        const imagePath = linkedImageMatch[2];
        const linkUrl = linkedImageMatch[3];
        
        console.log(`🔍 画像+リンク結合検出: ${imagePath} → ${linkUrl}`);
        
        // ローカルパスの画像をアップロード
        if (!imagePath.startsWith('http://') && !imagePath.startsWith('https://')) {
          const imageInfo = images.find(img => img.localPath === imagePath && img.hasLink);
          
          if (imageInfo && existsSync(imageInfo.absolutePath)) {
            console.log(`🖼️  画像+リンクを挿入中: ${imageInfo.absolutePath}`);
            
            // 画像をクリップボードにコピーしてペースト
            const imageBuffer = readFileSync(imageInfo.absolutePath);
            const base64Image = imageBuffer.toString('base64');
            
            await page.evaluate(async ({ base64 }) => {
              const response = await fetch(`data:image/png;base64,${base64}`);
              const blob = await response.blob();
              const item = new ClipboardItem({ 'image/png': blob });
              await navigator.clipboard.write([item]);
            }, { base64: base64Image });
            
            await page.waitForTimeout(1000);
            
            // ペースト
            const isMac = process.platform === 'darwin';
            if (isMac) {
              await page.keyboard.press('Meta+v');
            } else {
              await page.keyboard.press('Control+v');
            }
            
            await page.waitForTimeout(3000);
            console.log('✓ 画像挿入完了');
            
            // リンク設定をスキップ
            console.log(`🔗 リンク設定をスキップ: ${linkUrl}`);
            
            // 画像の後に改行
            if (!isLastLine) {
              await page.keyboard.press('Enter');
            }
            continue;
          }
        }
      }

      // 通常の画像マークダウンを検出: ![alt](path)
      const imageMatch = line.match(/!\[([^\]]*)\]\(([^)]+)\)/);
      if (imageMatch && !linkedImageMatch) {
        const imagePath = imageMatch[2];
        console.log(`🔍 画像マークダウン検出: ${imagePath}`);
        
        // ローカルパスの画像をアップロード
        if (!imagePath.startsWith('http://') && !imagePath.startsWith('https://')) {
          const imageInfo = images.find(img => img.localPath === imagePath && !img.hasLink);
          
          if (imageInfo && existsSync(imageInfo.absolutePath)) {
            console.log(`🖼️  画像を挿入中: ${imageInfo.absolutePath}`);
            
            const imageBuffer = readFileSync(imageInfo.absolutePath);
            const base64Image = imageBuffer.toString('base64');
            
            // クリップボードに画像を設定
            await page.evaluate(async ({ base64 }) => {
              const response = await fetch(`data:image/png;base64,${base64}`);
              const blob = await response.blob();
              const item = new ClipboardItem({ 'image/png': blob });
              await navigator.clipboard.write([item]);
            }, { base64: base64Image });
            
            await page.waitForTimeout(1000);
            
            // ペースト
            const isMac = process.platform === 'darwin';
            if (isMac) {
              await page.keyboard.press('Meta+v');
            } else {
              await page.keyboard.press('Control+v');
            }
            
            await page.waitForTimeout(3000);
            console.log('✓ 画像挿入完了');
            
            // 画像の後に改行
            if (!isLastLine) {
              await page.keyboard.press('Enter');
            }
            continue;
          }
        }
      }

      // YouTube動画URLを検出: @https://youtu.be/...
      if (line.startsWith('@')) {
        const youtubeUrl = line.substring(1); // "@"を除去
        console.log(`🎥 YouTube動画URL検出: ${youtubeUrl}`);
        
        // URLを入力してEnterで埋め込みに変換
        await page.keyboard.type(youtubeUrl, { delay: 20 });
        await page.keyboard.press('Enter');
        await page.waitForTimeout(2000); // 埋め込み変換を待つ
        
        console.log('✓ YouTube動画埋め込み完了');
        
        if (!isLastLine) {
          await page.keyboard.press('Enter');
        }
        continue;
      }

      // テキスト入力
      await page.keyboard.type(line, { delay: 20 });

      if (!isLastLine) {
        await page.keyboard.press('Enter');
      }
    }
    console.log('✓ 本文入力完了');

    if (isPublish) {
      console.log('📤 公開処理を開始...');
      
      // 「公開に進む」ボタンをクリック
      const proceedBtn = page.locator('button:has-text("公開に進む")').first();
      await proceedBtn.waitFor({ state: 'visible', timeout: 10000 });
      
      // ボタンが有効になるまで待機
      for (let i = 0; i < 20; i++) {
        if (await proceedBtn.isEnabled()) break;
        await page.waitForTimeout(100);
      }
      
      await proceedBtn.click();
      console.log('✓ 公開設定ページに移動');
      await page.waitForTimeout(3000);
      
      // 公開ページへの遷移を待つ
      await Promise.race([
        page.waitForURL(/\/publish/i, { timeout: 10000 }).catch(() => {}),
        page.locator('button:has-text("投稿する")').first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => {}),
      ]);
      
      // 「投稿する」ボタンをクリック
      console.log('📝 投稿中...');
      const publishBtn = page.locator('button:has-text("投稿する")').first();
      await publishBtn.waitFor({ state: 'visible', timeout: 10000 });
      
      // ボタンが有効になるまで待機
      for (let i = 0; i < 20; i++) {
        if (await publishBtn.isEnabled()) break;
        await page.waitForTimeout(100);
      }
      
      await publishBtn.click();
      console.log('✓ 投稿ボタンをクリック');
      
      // 確認ダイアログやモーダルが表示されるかチェック
      await page.waitForTimeout(2000);
      
      // 確認ボタンを探してクリック
      try {
        const confirmBtn = page.locator('button:has-text("投稿する"), button:has-text("確認"), button:has-text("OK"), button[type="submit"]').last();
        if (await confirmBtn.isVisible({ timeout: 3000 })) {
          console.log('確認ボタンを検出しました');
          await confirmBtn.click();
          console.log('✓ 確認ボタンをクリック');
          await page.waitForTimeout(3000);
        }
      } catch (e) {
        console.log('確認ボタンは不要でした');
      }
      
      // 投稿完了を待つ
      await page.waitForTimeout(3000);
      
      console.log('✅ 記事を公開しました！');
      console.log(`🔗 URL: ${page.url()}\n`);
    } else {
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
    }

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

const markdownPath = process.argv[2] || '/Users/sakonhiroki/Projects/test_note_article.md';
const username = process.argv[3] || 'bestinksalesman';
const password = process.argv[4] || 'Hsakon0419';
const statePath = process.argv[5] || '/Users/sakonhiroki/.note-state.json';
const isPublish = process.argv[6] === '--publish' || process.argv[6] === '-p';

console.log(`モード: ${isPublish ? '公開' : '下書き保存'}\n`);

saveDraft(markdownPath, username, password, statePath, isPublish).catch(console.error);
