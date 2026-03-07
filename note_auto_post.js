import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, unlinkSync } from 'fs';
import * as path from 'path';
import * as os from 'os';
import https from 'https';
import http from 'http';

// リモート画像をダウンロードする関数
async function downloadImage(url) {
  return new Promise((resolve, reject) => {
    const tempPath = path.join(os.tmpdir(), `temp-${Date.now()}-${Math.random().toString(36).substring(7)}.jpg`);
    
    const protocol = url.startsWith('https') ? https : http;
    
    protocol.get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }
      
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        writeFileSync(tempPath, Buffer.concat(chunks));
        resolve(tempPath);
      });
    }).on('error', reject);
  });
}

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

async function refreshTableOfContents(page, bodyHasHeadings) {
  if (!bodyHasHeadings) {
    console.log('ℹ️  見出しがないため目次をスキップします');
    return;
  }

  try {
    const existingToc = page.locator('table-of-contents');
    const existingCount = await existingToc.count();
    if (existingCount > 0) {
      console.log(`🧹 既存の目次を削除しています (${existingCount}件)`);
      for (let i = existingCount - 1; i >= 0; i--) {
        const tocBlock = existingToc.nth(i);
        try {
          await tocBlock.click({ timeout: 2000 });
          await page.waitForTimeout(300);
          await page.keyboard.press('Delete');
          await page.waitForTimeout(300);
        } catch (innerError) {
          console.log(`⚠️  目次削除に失敗: ${innerError.message}`);
        }
      }
    }

    console.log('📋 目次を挿入中（本文入力後）...');
    const bodyBox = page.locator('div[contenteditable="true"][role="textbox"]').first();
    await bodyBox.click({ force: true });

    const isMac = process.platform === 'darwin';
    const goTopShortcut = isMac ? 'Meta+ArrowUp' : 'Control+Home';

    await page.keyboard.press(goTopShortcut);
    await page.waitForTimeout(300);

    // 空行を挿入してブロックメニューを利用しやすくする
    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(200);

    const menuButton = page.locator('button[aria-label="メニューを開く"]').first();
    await menuButton.waitFor({ state: 'visible', timeout: 5000 });
    await menuButton.click();
    await page.waitForTimeout(500);
    console.log('✓ メニューを開きました');

    const tocButton = page.locator('button:has-text("目次")').first();
    await tocButton.waitFor({ state: 'visible', timeout: 5000 });
    await tocButton.click();
    await page.waitForTimeout(2000);
    console.log('✓ 目次を挿入しました');

    // 目次の直後に本文が始まるように改行を追加
    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);
  } catch (error) {
    console.log('⚠️  目次更新エラー:', error.message);
  }
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
    body: body,
    tags: tags.filter(Boolean),
    thumbnail: thumbnail,
  };
}

async function saveDraft(markdownPath, username, password, statePath, isPublish = false, magazineName = null) {
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

  // GitHub Actions環境ではheadless: true、ローカルではheadless: false
  const isCI = process.env.CI === 'true';
  const browser = await chromium.launch({
    headless: isCI,
    args: [
      '--lang=ja-JP',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu'
    ],
  });

  try {
    // 認証状態ファイルがあれば読み込む
    let contextOptions = {
      locale: 'ja-JP',
      viewport: { width: 1280, height: 800 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
    await page.goto('https://editor.note.com/new', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);

    // ログインページにリダイレクトされたかチェック
    const currentUrl = page.url();
    console.log(`現在のURL: ${currentUrl}`);

    if (currentUrl.includes('/login')) {
      console.log('\n🔐 ログインが必要です。自動ログイン中...');
      
      await page.waitForTimeout(2000);
      
      // メールアドレスまたはnoteIDを入力
      console.log('ID入力欄を探しています...');
      try {
        const emailInput = await page.locator('input[placeholder*="note ID"], input[placeholder*="mail"]').first();
        await emailInput.waitFor({ state: 'visible', timeout: 15000 });
        await emailInput.click();
        await page.waitForTimeout(500);
        await emailInput.type(username, { delay: 100 });
        console.log('✓ ID入力完了');
        await page.waitForTimeout(1000);
      } catch (error) {
        console.log(`❌ ID入力エラー: ${error.message}`);
        throw error;
      }

      // パスワードを入力
      console.log('パスワード入力欄を探しています...');
      try {
        const passwordInput = await page.locator('input[type="password"]').first();
        await passwordInput.waitFor({ state: 'visible', timeout: 15000 });
        await passwordInput.click();
        await page.waitForTimeout(500);
        await passwordInput.type(password, { delay: 100 });
        console.log('✓ パスワード入力完了');
        await page.waitForTimeout(1000);
      } catch (error) {
        console.log(`❌ パスワード入力エラー: ${error.message}`);
        throw error;
      }

      // ログインボタンをクリック
      console.log('ログインボタンを探しています...');
      try {
        const loginButton = await page.locator('button[type="submit"], button:has-text("ログイン")').first();
        await loginButton.waitFor({ state: 'visible', timeout: 15000 });
        await loginButton.click();
        console.log('✓ ログインボタンをクリック');
      } catch (error) {
        console.log(`❌ ログインボタンクリックエラー: ${error.message}`);
        throw error;
      }
      
      // ログイン完了を待機（リダイレクトを待つ）
      console.log('ログイン完了を待機中...');
      await page.waitForTimeout(5000);
      
      // ログイン成功を確認（ログインページからリダイレクトされたか）
      const afterLoginUrl = page.url();
      console.log(`📍 ログイン後のURL: ${afterLoginUrl}`);
      if (afterLoginUrl.includes('/login')) {
        console.log('⚠️  まだログインページにいます。追加の待機時間を設けます...');
        await page.waitForTimeout(5000);
      }
      
      // 認証状態を保存
      const storageState = await context.storageState();
      writeFileSync(statePath, JSON.stringify(storageState, null, 2));
      console.log(`✓ 認証状態を保存: ${statePath}\n`);

      // 新規記事作成ページに再度移動
      console.log('🌐 editor.note.com/new に再度移動中...');
      await page.goto('https://editor.note.com/new', { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);
    }

    // 見出し画像を設定（タイトル入力の前）
    if (thumbnail) {
      const resolvedMarkdownPath = path.resolve(markdownPath);
      const articleDir = path.dirname(resolvedMarkdownPath);
      const cleanedThumbnail = thumbnail.replace(/^\.?\//, '');
      const candidates = [
        path.resolve(process.cwd(), cleanedThumbnail),
        path.resolve(articleDir, cleanedThumbnail),
        path.resolve(process.cwd(), 'daily-articles', cleanedThumbnail),
        path.resolve(process.cwd(), '..', cleanedThumbnail)
      ];
      
      console.log('🧭 見出し画像の候補パスをチェック:');
      const thumbnailPath = candidates.find((candidate) => {
        const exists = existsSync(candidate);
        console.log(`   - ${candidate} ${exists ? '✓' : '✗'}`);
        return exists;
      });
      
      if (thumbnailPath) {
        console.log('🖼️  見出し画像を設定中（タイトルの上）...');
        console.log(`   使用ファイル: ${thumbnailPath}`);
        try {
          // ページが完全に読み込まれるまで待機
          await page.waitForTimeout(3000);
          
          // タイトル入力欄が表示されるまで待つ
          await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 30000 });
          await page.waitForTimeout(1000);
          
          // 見出し画像ボタンを探してクリック（複数のセレクターを試す）
          let thumbnailButton = null;
          
          // まず、ページのスクリーンショットを取得してデバッグ（エラーは無視）
          try {
            if (!process.env.CI) {
              const screenshotPath = path.join(os.tmpdir(), `note-editor-before-thumbnail-${Date.now()}.png`);
              await page.screenshot({ path: screenshotPath, fullPage: false });
              console.log(`📸 デバッグ用スクリーンショット保存: ${screenshotPath}`);
            }
          } catch (e) {
            // スクリーンショットエラーは無視して続行
            console.log('⚠️  スクリーンショット取得エラー（続行）:', e.message);
          }
          
          const buttonSelectors = [
            'button[aria-label="画像を追加"]',
            'button[aria-label*="画像"]',
            'button:has-text("画像")',
            'button:has-text("画像を追加")',
            'div[class*="thumbnail"] button',
            'div[class*="header"] button[aria-label*="画像"]',
            'button[class*="image"]',
            'button[class*="add-image"]',
            'div[class*="title"] + div button',
            'div[class*="editor-header"] button',
            // より具体的なセレクターを追加
            'div[data-testid*="thumbnail"] button',
            'div[data-testid*="image"] button',
            '[role="button"][aria-label*="画像"]',
          ];
          
          console.log('🔍 見出し画像ボタンを探しています...');
          for (const selector of buttonSelectors) {
            try {
              const button = page.locator(selector).first();
              if (await button.isVisible({ timeout: 2000 })) {
                console.log(`✓ 見出し画像ボタン発見: ${selector}`);
                thumbnailButton = button;
                break;
              }
            } catch (e) {
              // エラーは無視して次のセレクターを試す
              continue;
            }
          }
          
          if (!thumbnailButton) {
            // タイトル入力欄の周辺を詳しく探す
            console.log('タイトル入力欄の周辺を詳しく探しています...');
            try {
              const titleArea = page.locator('textarea[placeholder*="タイトル"]').first();
              if (await titleArea.isVisible({ timeout: 2000 })) {
                // タイトル入力欄の親要素から画像追加ボタンを探す
                const parentElement = titleArea.locator('..');
                const imageButton = parentElement.locator('button, div[role="button"], [aria-label*="画像"]').first();
                if (await imageButton.isVisible({ timeout: 2000 })) {
                  thumbnailButton = imageButton;
                  console.log('✓ タイトル上の画像追加ボタンを発見');
                }
              }
              
              // タイトル入力欄の前にある要素を探す
              if (!thumbnailButton) {
                const titleAreaRect = await titleArea.boundingBox();
                if (titleAreaRect) {
                  // タイトル入力欄の上にあるボタンを探す
                  const buttonsAbove = await page.locator('button').all();
                  for (const btn of buttonsAbove) {
                    const btnRect = await btn.boundingBox();
                    if (btnRect && btnRect.y < titleAreaRect.y && btnRect.y > titleAreaRect.y - 100) {
                      const ariaLabel = await btn.getAttribute('aria-label');
                      if (ariaLabel && (ariaLabel.includes('画像') || ariaLabel.includes('image'))) {
                        thumbnailButton = btn;
                        console.log('✓ タイトル上の画像ボタンを発見（位置ベース）');
                        break;
                      }
                    }
                  }
                }
              }
            } catch (e) {
              console.log('⚠️  タイトル周辺の検索エラー:', e.message);
            }
          }
          
          if (thumbnailButton) {
            console.log('見出し画像ボタンをクリック中...');
            await thumbnailButton.click();
            await page.waitForTimeout(2000);
            
            // ファイル入力要素を直接探す（モーダルが開く前でも）
            let fileInput = null;
            const fileInputSelectors = [
              'input[type="file"]',
              'input[accept*="image"]',
              'input[accept*="png"]',
              'input[accept*="jpg"]',
            ];
            
            for (const selector of fileInputSelectors) {
              try {
                const input = page.locator(selector).first();
                if (await input.isVisible({ timeout: 2000 })) {
                  fileInput = input;
                  console.log(`✓ ファイル入力要素発見: ${selector}`);
                  break;
                }
              } catch (e) {
                continue;
              }
            }
            
            // ファイル入力要素が見つからない場合は、モーダルを待つ
            if (!fileInput) {
              console.log('ファイル入力要素を待機中...');
              await page.waitForTimeout(2000);
              
              // 「画像をアップロード」ボタンをクリック
              try {
                const uploadButton = page.locator('button:has-text("画像をアップロード"), button:has-text("アップロード")').first();
                if (await uploadButton.isVisible({ timeout: 3000 })) {
                  console.log('「画像をアップロード」ボタンをクリック中...');
                  await uploadButton.click();
                  await page.waitForTimeout(2000);
                }
              } catch (e) {
                console.log('「画像をアップロード」ボタンが見つかりませんでした（スキップ）');
              }
              
              // ファイル入力要素を再度探す
              fileInput = page.locator('input[type="file"]').first();
              await fileInput.waitFor({ state: 'visible', timeout: 5000 });
            }
            
            // ファイルを設定
            console.log(`画像ファイルを設定中: ${thumbnailPath}`);
            await fileInput.setInputFiles(thumbnailPath);
            console.log('✓ ファイル設定完了');
            await page.waitForTimeout(3000);
            
            // アップロード完了を待つ（画像が表示されるまで）
            console.log('画像のアップロード完了を待機中...');
            await page.waitForTimeout(5000);
            
            // クロップモーダル内の保存ボタンをクリック
            console.log('クロップモーダル内の保存ボタンを待っています...');
            await page.waitForTimeout(2000);
            
            try {
              // クロップモーダル内の保存ボタンを探す（複数のセレクターを試す）
              const saveButtonSelectors = [
                '.CropModal__overlay button:has-text("保存")',
                '.ReactModal__Overlay button:has-text("保存")',
                'button:has-text("保存")',
                'button:has-text("確定")',
                'button[type="submit"]',
              ];
              
              let saveButton = null;
              for (const selector of saveButtonSelectors) {
                try {
                  const button = page.locator(selector).last();
                  if (await button.isVisible({ timeout: 2000 })) {
                    saveButton = button;
                    console.log(`✓ 保存ボタン発見: ${selector}`);
                    break;
                  }
                } catch (e) {
                  continue;
                }
              }
              
              if (saveButton) {
                console.log('クロップモーダルの保存ボタンをクリックしています...');
                await saveButton.click();
                await page.waitForTimeout(2000);
                console.log('✓ クロップモーダルの保存ボタンをクリックしました');
              } else {
                console.log('⚠️  保存ボタンが見つかりませんでした（Enterキーで試行）');
                await page.keyboard.press('Enter');
                await page.waitForTimeout(1000);
              }
            } catch (e) {
              console.log('⚠️  保存ボタンクリックエラー:', e.message);
              // Enterキーで試行
              await page.keyboard.press('Enter');
              await page.waitForTimeout(1000);
            }
            
            // モーダルが閉じるまで待つ
            await page.waitForTimeout(2000);
            
            // 画像が設定されたか確認
            const imageElements = await page.locator('img').count();
            if (imageElements > 0) {
              console.log(`✓ 画像が設定されました（${imageElements}個の画像要素を検出）`);
            } else {
              console.log('⚠️  画像要素が見つかりませんでした');
            }
            
            console.log('✓ 見出し画像設定完了');
          } else {
            throw new Error('見出し画像ボタンが見つかりませんでした');
          }
        } catch (error) {
          console.log('⚠️  見出し画像設定エラー:', error.message);
          console.log('見出し画像なしで続行します...');
        }
      } else {
        console.log('⚠️  見出し画像ファイルがいずれの候補パスにも存在しませんでした');
      }
    }

    console.log('📋 タイトル入力中...');
    await page.waitForSelector('textarea[placeholder*="タイトル"]', { timeout: 30000 });
    await page.fill('textarea[placeholder*="タイトル"]', title);
    console.log('✓ タイトル入力完了');

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
    const hasHeadings = lines.some(line => line.trim().startsWith('### '));
    
    console.log(`📝 本文を入力中... (全${lines.length}行)`);
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const isLastLine = i === lines.length - 1;
      const isMac = process.platform === 'darwin';
      
      // 進捗表示（10行ごと）
      if (i > 0 && i % 10 === 0) {
        console.log(`  進捗: ${i}/${lines.length}行 (${Math.round(i/lines.length*100)}%)`);
      }

      // 画像+リンク結合マークダウンを検出: [![alt](path)](url)
      const linkedImageMatch = line.match(/\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)/);
      if (linkedImageMatch) {
        const alt = linkedImageMatch[1];
        const imagePath = linkedImageMatch[2];
        const linkUrl = linkedImageMatch[3];
        
        console.log(`🔍 画像+リンク結合検出: ${imagePath} → ${linkUrl}`);
        
        let actualImagePath = null;
        
        // リモートURL画像の場合はダウンロード
        if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
          console.log(`🌐 リモート画像をダウンロード中: ${imagePath}`);
          try {
            actualImagePath = await downloadImage(imagePath);
            console.log(`✓ ダウンロード完了: ${actualImagePath}`);
          } catch (error) {
            console.log(`⚠️  ダウンロード失敗: ${error.message}`);
            // ダウンロード失敗時はMarkdownをそのまま入力
            await page.keyboard.type(line, { delay: 20 });
            if (!isLastLine) {
              await page.keyboard.press('Enter');
            }
            continue;
          }
        } else {
          // ローカルパスの場合
          const absolutePath = path.resolve(path.dirname(markdownPath), imagePath);
          if (existsSync(absolutePath)) {
            actualImagePath = absolutePath;
          }
        }
        
        if (actualImagePath && existsSync(actualImagePath)) {
          console.log(`🖼️  画像+リンクを挿入中: ${actualImagePath}`);
          
          try {
            // ファイルアップロード
            const fileInput = await page.$('input[type="file"]');
            if (fileInput) {
              await fileInput.setInputFiles(actualImagePath);
              await page.waitForTimeout(3000); // アップロード完了を待つ
              console.log(`✅ 画像をアップロード完了`);
              
              // 画像がリンク付きの場合、リンクを設定
              if (linkUrl) {
                console.log(`🔗 リンクを設定中: ${linkUrl}`);
                
                try {
                  // 挿入された画像を選択
                  await page.waitForTimeout(1000);
                  
                  // 画像をクリックして選択
                  const uploadedImage = page.locator('img').last();
                  await uploadedImage.click();
                  await page.waitForTimeout(500);
                  
                  // リンク設定ボタンを探してクリック
                  const linkButton = page.locator('button[aria-label*="リンク"], button:has-text("リンク")').first();
                  if (await linkButton.isVisible({ timeout: 2000 })) {
                    await linkButton.click();
                    await page.waitForTimeout(500);
                    
                    // リンクURLを入力
                    const linkInput = page.locator('input[type="text"], input[type="url"]').last();
                    await linkInput.fill(linkUrl);
                    await page.waitForTimeout(500);
                    
                    // 確定ボタンをクリック
                    const confirmButton = page.locator('button:has-text("確定"), button:has-text("OK"), button[type="submit"]').last();
                    if (await confirmButton.isVisible({ timeout: 2000 })) {
                      await confirmButton.click();
                      await page.waitForTimeout(500);
                      console.log(`✓ リンク設定完了`);
                    } else {
                      // Enterキーで確定
                      await page.keyboard.press('Enter');
                      console.log(`✓ リンク設定完了（Enter）`);
                    }
                  } else {
                    console.log(`⚠️  リンクボタンが見つかりません。リンクなしで続行します。`);
                  }
                } catch (linkError) {
                  console.log(`⚠️  リンク設定エラー: ${linkError.message}`);
                }
              }
              
              // 画像の後に改行（カーソルを次の行に移動）
              await page.keyboard.press('ArrowDown'); // 画像の下に移動
              await page.waitForTimeout(300);
              
            } else {
              console.log(`⚠️  ファイルアップロード要素が見つかりません。`);
            }
          } catch (uploadError) {
            console.log(`⚠️  画像アップロードエラー: ${uploadError.message}`);
          }
          
          // リモート画像の一時ファイルを削除
          if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
            try {
              unlinkSync(actualImagePath);
              console.log(`🗑️  一時ファイル削除: ${actualImagePath}`);
            } catch (e) {
              // 削除失敗は無視
            }
          }
          
          if (!isLastLine) {
            await page.keyboard.press('Enter');
          }
          continue;
        } else {
          console.log(`⚠️  画像ファイルが見つかりません: ${imagePath}`);
          // 画像が見つからない場合はMarkdownをそのまま入力
          await page.keyboard.type(line, { delay: 20 });
          if (!isLastLine) {
            await page.keyboard.press('Enter');
          }
          continue;
        }
      }

      // 通常の画像マークダウンを検出: ![alt](path)
      const imageMatch = line.match(/!\[([^\]]*)\]\(([^)]+)\)/);
      if (imageMatch && !linkedImageMatch) {
        const imagePath = imageMatch[2];
        console.log(`🔍 画像マークダウン検出: ${imagePath}`);
        
        let actualImagePath = null;
        
        // リモートURL画像の場合はダウンロード
        if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
          console.log(`🌐 リモート画像をダウンロード中: ${imagePath}`);
          try {
            actualImagePath = await downloadImage(imagePath);
            console.log(`✓ ダウンロード完了: ${actualImagePath}`);
          } catch (error) {
            console.log(`⚠️  ダウンロード失敗: ${error.message}`);
            // ダウンロード失敗時はMarkdownをそのまま入力
            await page.keyboard.type(line, { delay: 20 });
            if (!isLastLine) {
              await page.keyboard.press('Enter');
            }
            continue;
          }
        } else {
          // ローカルパスの場合
          const imageInfo = images.find(img => img.localPath === imagePath && !img.hasLink);
          if (imageInfo && existsSync(imageInfo.absolutePath)) {
            actualImagePath = imageInfo.absolutePath;
          }
        }
        
        if (actualImagePath && existsSync(actualImagePath)) {
          console.log(`🖼️  画像を挿入中: ${actualImagePath}`);
          
          try {
            // ファイルアップロード
            const fileInput = await page.$('input[type="file"]');
            if (fileInput) {
              await fileInput.setInputFiles(actualImagePath);
              await page.waitForTimeout(3000); // アップロード完了を待つ
              console.log(`✅ 画像をアップロード完了`);
            } else {
              console.log(`⚠️  ファイルアップロード要素が見つかりません。`);
            }
          } catch (uploadError) {
            console.log(`⚠️  画像アップロードエラー: ${uploadError.message}`);
          }
          
          // リモート画像の一時ファイルを削除
          if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
            try {
              unlinkSync(actualImagePath);
              console.log(`🗑️  一時ファイル削除: ${actualImagePath}`);
            } catch (e) {
              // 削除失敗は無視
            }
          }
          
          if (!isLastLine) {
            await page.keyboard.press('Enter');
          }
          continue;
        } else {
          console.log(`⚠️  画像ファイルが見つかりません: ${imagePath}`);
          // 画像が見つからない場合はMarkdownをそのまま入力
          await page.keyboard.type(line, { delay: 20 });
          if (!isLastLine) {
            await page.keyboard.press('Enter');
          }
          continue;
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

      // テキストリンクマークダウンを検出し、noteのリンク機能で埋め込み
      const linkRegex = /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g;
      let match;
      let cursor = 0;
      let handledLink = false;

      while ((match = linkRegex.exec(line)) !== null) {
        handledLink = true;

        const beforeText = line.slice(cursor, match.index);
        if (beforeText) {
          await page.keyboard.type(beforeText, { delay: 20 });
        }

        const label = match[1];
        const linkUrl = match[2];
        console.log(`🔗 テキストリンクを挿入中: ${label} → ${linkUrl}`);

        await page.keyboard.type(label, { delay: 20 });
        await page.waitForTimeout(100);

        // 入力したラベル分だけ選択
        await page.keyboard.down('Shift');
        for (let s = 0; s < label.length; s++) {
          await page.keyboard.press('ArrowLeft');
        }
        await page.keyboard.up('Shift');
        await page.waitForTimeout(100);

        // リンク挿入ショートカットを実行
        await page.keyboard.press(isMac ? 'Meta+K' : 'Control+K');
        await page.waitForTimeout(200);

        let linkApplied = false;
        try {
          const linkInput = page.locator('input[placeholder*="URL"], input[type="url"], input[aria-label*="URL"], div[role="dialog"] input');
          await linkInput.waitFor({ state: 'visible', timeout: 2000 });
          await linkInput.fill(linkUrl);
          await page.waitForTimeout(100);
          await page.keyboard.press('Enter');
          linkApplied = true;
        } catch (error) {
          console.log('⚠️  リンク入力UIが見つからなかったためフォールバックします');
        }

        if (!linkApplied) {
          await page.evaluate((url) => {
            document.execCommand('createLink', false, url);
          }, linkUrl);
        }

        await page.waitForTimeout(150);
        await page.keyboard.press('ArrowRight');

        cursor = match.index + match[0].length;
      }

      if (handledLink) {
        const remainingText = line.slice(cursor);
        if (remainingText) {
          await page.keyboard.type(remainingText, { delay: 20 });
        }

        if (!isLastLine) {
          await page.keyboard.press('Enter');
          if (line.match(/^\d+\.\s/)) {
            await page.waitForTimeout(50);
          }
        }
        continue;
      }

      // テキスト入力
      await page.keyboard.type(line, { delay: 20 });

      if (!isLastLine) {
        await page.keyboard.press('Enter');
        // 番号付きリスト（1. 2. など）の場合は、少し待機
        if (line.match(/^\d+\.\s/)) {
          await page.waitForTimeout(50);
        }
      }
    }
    await refreshTableOfContents(page, hasHeadings);
    console.log('✓ 本文入力完了');

    let finalArticleUrl = '';

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
      
      // マガジン選択（公開設定ページで、「投稿する」ボタンをクリックする前）
      if (magazineName) {
        console.log(`📚 マガジン「${magazineName}」に追加中...`);
        try {
          // 公開設定ページが完全に読み込まれるまで待機
          await page.waitForTimeout(3000);
          
          // ページのURLを確認（デバッグ用）
          const currentUrl = page.url();
          console.log(`📍 現在のURL: ${currentUrl}`);
          
          if (!currentUrl.includes('/publish') && !currentUrl.includes('/editor')) {
            console.log(`⚠️  公開設定ページではない可能性があります。マガジン選択をスキップします。`);
          } else {
          
          // マガジン選択UIを探す（複数のセレクターを試す）
          let magazineSelected = false;
          
          // セレクター1: マガジン選択ボタン（「マガジンを選択」「マガジンに追加」など）
          const magazineButtons = [
            'button:has-text("マガジンを選択")',
            'button:has-text("マガジンに追加")',
            'button:has-text("マガジン")',
            'button[aria-label*="マガジン"]',
            'div[class*="magazine"] button',
            'label:has-text("マガジン") + *',
          ];
          
          for (const selector of magazineButtons) {
            try {
              const button = page.locator(selector).first();
              if (await button.isVisible({ timeout: 2000 })) {
                console.log(`✓ マガジンボタン発見: ${selector}`);
                await button.click();
                await page.waitForTimeout(1500);
                
                // クリック後にモーダルやドロップダウンが表示される
                // マガジン名で検索
                const searchInputs = [
                  'input[type="text"]',
                  'input[placeholder*="検索"]',
                  'input[placeholder*="マガジン"]',
                  'input[type="search"]',
                ];
                
                for (const inputSelector of searchInputs) {
                  try {
                    const input = page.locator(inputSelector).first();
                    if (await input.isVisible({ timeout: 1000 })) {
                      await input.fill(magazineName);
                      await page.waitForTimeout(1000);
                      console.log(`✓ マガジン名で検索: ${magazineName}`);
                      break;
                    }
                  } catch (e) {
                    // 次のセレクターを試す
                  }
                }
                
                // マガジン名に一致する項目をクリック
                const magazineItems = [
                  `button:has-text("${magazineName}")`,
                  `div:has-text("${magazineName}")`,
                  `li:has-text("${magazineName}")`,
                  `a:has-text("${magazineName}")`,
                  `[role="option"]:has-text("${magazineName}")`,
                ];
                
                for (const itemSelector of magazineItems) {
                  try {
                    const item = page.locator(itemSelector).first();
                    if (await item.isVisible({ timeout: 2000 })) {
                      await item.click();
                      await page.waitForTimeout(1000);
                      console.log(`✓ マガジン「${magazineName}」を選択しました`);
                      magazineSelected = true;
                      break;
                    }
                  } catch (e) {
                    // 次のセレクターを試す
                  }
                }
                
                if (magazineSelected) {
                  // モーダルを閉じる（Escキーまたは外側クリック）
                  await page.keyboard.press('Escape');
                  await page.waitForTimeout(500);
                  break;
                }
              }
            } catch (e) {
              // 次のセレクターを試す
              continue;
            }
          }
          
          // セレクター2: select要素の場合
          if (!magazineSelected) {
            try {
              const selectElement = page.locator('select').first();
              if (await selectElement.isVisible({ timeout: 2000 })) {
                await selectElement.selectOption({ label: magazineName });
                console.log(`✓ マガジン「${magazineName}」を選択しました（select要素）`);
                magazineSelected = true;
              }
            } catch (e) {
              // select要素がない場合は無視
            }
          }
          
            if (!magazineSelected) {
              console.log(`⚠️  マガジン「${magazineName}」の選択に失敗しました`);
              console.log('マガジンなしで続行します...');
            }
          }
          
          await page.waitForTimeout(1000);
        } catch (error) {
          console.log(`⚠️  マガジン選択エラー: ${error.message}`);
          console.log(`エラースタック: ${error.stack}`);
          console.log('マガジンなしで続行します...');
          // エラーが発生しても処理を続行（致命的なエラーではない）
        }
      }
      
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
      
      finalArticleUrl = page.url();
      console.log('✅ 記事を公開しました！');
      console.log(`🔗 URL: ${finalArticleUrl}\n`);
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

      finalArticleUrl = page.url();
      console.log('✓ 下書き保存完了！');
      console.log(`🔗 URL: ${finalArticleUrl}\n`);
    }

    if (finalArticleUrl) {
      console.log(`NOTE_ARTICLE_URL=${finalArticleUrl}`);
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
    console.error('スタックトレース:', error.stack);
    try {
      const errorPath = path.join(os.tmpdir(), `error-${Date.now()}.png`);
      await page.screenshot({ path: errorPath, fullPage: true });
      console.log(`エラースクリーンショット: ${errorPath}`);
    } catch (screenshotError) {
      console.log('スクリーンショットの保存に失敗しました');
    }
    throw error; // エラーを再スロー
  } finally {
    await browser.close();
  }
}

// コマンドライン引数の解析
let markdownPath = null;
let username = null;
let password = null;
let statePath = null;
let isPublish = false;
let magazineName = null;

for (let i = 2; i < process.argv.length; i++) {
  const arg = process.argv[i];
  if (arg === '--publish' || arg === '-p') {
    isPublish = true;
  } else if (arg === '--magazine' || arg === '-m') {
    magazineName = process.argv[++i];
  } else if (!markdownPath) {
    markdownPath = arg;
  } else if (!username) {
    username = arg;
  } else if (!password) {
    password = arg;
  } else if (!statePath) {
    statePath = arg;
  }
}

// デフォルト値
markdownPath = markdownPath || '/Users/sakonhiroki/Projects/test_note_article.md';
username = username || 'bestinksalesman';
password = password || 'Hsakon0419';
statePath = statePath || '/Users/sakonhiroki/.note-state.json';

// 環境変数からマガジン名を取得（優先）
if (!magazineName && process.env.NOTE_MAGAZINE_NAME) {
  magazineName = process.env.NOTE_MAGAZINE_NAME;
}

console.log(`モード: ${isPublish ? '公開' : '下書き保存'}`);
if (magazineName) {
  console.log(`マガジン: ${magazineName}`);
}
console.log('');

saveDraft(markdownPath, username, password, statePath, isPublish, magazineName).catch(error => {
  console.error('処理失敗:', error);
  process.exit(1);
});
