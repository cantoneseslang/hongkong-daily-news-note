import { chromium } from 'playwright';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import path from 'path';
import os from 'os';

const MAX_TWEET_LENGTH = 270;
const COMPOSE_URL = 'https://x.com/compose/post';

function parseMarkdown(markdown) {
  const lines = markdown.split('\n');
  let idx = 0;
  let frontMatterTitle = '';

  if (lines[idx]?.trim() === '---') {
    idx += 1;
    while (idx < lines.length && lines[idx].trim() !== '---') {
      const line = lines[idx];
      if (line.startsWith('title:')) {
        frontMatterTitle = line.slice(6).trim().replace(/^["']|["']$/g, '');
      }
      idx += 1;
    }
    if (idx < lines.length && lines[idx].trim() === '---') {
      idx += 1;
    }
  }

  const bodyLines = lines.slice(idx);
  let title = frontMatterTitle;
  const contentLines = [];

  for (const line of bodyLines) {
    if (!title && line.startsWith('# ')) {
      title = line.slice(2).trim();
      continue;
    }
    contentLines.push(line);
  }

  return {
    title: title || '毎日AI香港ピックアップニュース',
    body: contentLines.join('\n'),
  };
}

function extractDateLabel(title, filePath) {
  const titleMatch = title.match(/(\d{4})年(\d{2})月(\d{2})日/);
  if (titleMatch) {
    const [, year, month, day] = titleMatch;
    return `${Number(month)}/${Number(day)}`;
  }

  const fileMatch = path.basename(filePath).match(/(\d{4})-(\d{2})-(\d{2})/);
  if (fileMatch) {
    const [, , month, day] = fileMatch;
    return `${Number(month)}/${Number(day)}`;
  }

  return '';
}

function cleanHeading(text) {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^[0-9０-９]+\.\s*/u, '')
    .replace(/\s+/g, ' ')
    .replace(/\*\*/g, '')
    .trim();
}

function extractIndexItems(body) {
  const lines = body.split('\n');
  const items = [];
  let inCantoneseSection = false;

  if (body.includes('## 本日の香港の天気')) {
    items.push('本日の香港の天気');
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line.startsWith('## 広東語学習者向け情報')) {
      inCantoneseSection = true;
      continue;
    }
    if (inCantoneseSection) {
      continue;
    }

    if (!line.startsWith('### ')) {
      continue;
    }

    const heading = cleanHeading(line.slice(4));
    if (!heading || heading === '天気警報') {
      continue;
    }

    items.push(heading);
  }

  return [...new Set(items)];
}

function shortenHeadline(text, maxLength) {
  const chars = Array.from(text);
  if (chars.length <= maxLength) {
    return text;
  }
  return `${chars.slice(0, Math.max(0, maxLength - 1)).join('')}…`;
}

function tweetLength(text) {
  return Array.from(text).length;
}

function buildTweet({ title, items, noteUrl, filePath }) {
  const dateLabel = extractDateLabel(title, filePath);
  const header = dateLabel
    ? `毎日AI香港ピックアップニュース ${dateLabel}`
    : '毎日AI香港ピックアップニュース';

  const lines = [header, '', '目次'];
  let shown = 0;
  const totalItems = items.length;

  for (const item of items) {
    const remainingAfterThis = totalItems - (shown + 1);
    const footer = remainingAfterThis > 0
      ? `今日のニュースさらに${remainingAfterThis}記事`
      : '今日のニュースはこちら';

    const shortItem = shortenHeadline(item, 34);
    const candidateLines = [
      ...lines,
      `・${shortItem}`,
      '',
      footer,
      noteUrl,
    ];
    const candidateText = candidateLines.join('\n');
    if (tweetLength(candidateText) > MAX_TWEET_LENGTH) {
      break;
    }

    lines.push(`・${shortItem}`);
    shown += 1;
  }

  const remaining = Math.max(0, totalItems - shown);
  lines.push('');
  lines.push(remaining > 0 ? `今日のニュースさらに${remaining}記事` : '今日のニュースはこちら');
  lines.push(noteUrl);

  return lines.join('\n');
}

async function postToX({ articlePath, noteUrl, dryRun }) {
  const markdown = readFileSync(articlePath, 'utf-8');
  const { title, body } = parseMarkdown(markdown);
  const items = extractIndexItems(body);

  if (items.length === 0) {
    throw new Error('目次に使える見出しを記事から抽出できませんでした');
  }

  const tweetText = buildTweet({
    title,
    items,
    noteUrl,
    filePath: articlePath,
  });

  console.log('🧵 X投稿プレビュー:');
  console.log('----------------------------------------');
  console.log(tweetText);
  console.log('----------------------------------------');
  console.log(`文字数: ${tweetLength(tweetText)}`);

  if (dryRun) {
    console.log('DRY_RUN=true のため、Xへの実投稿はスキップしました');
    return;
  }

  const statePath = process.env.X_STATE_PATH || process.env.X_AUTH_STATE_PATH || '';
  const loginId = process.env.X_USERNAME || process.env.X_EMAIL || process.env.X_LOGIN || '';
  const password = process.env.X_PASSWORD || '';
  const handle = process.env.X_HANDLE || (loginId.includes('@') ? '' : loginId.replace(/^@/, ''));

  if ((!statePath || !existsSync(statePath)) && (!loginId || !password)) {
    throw new Error('Xログイン情報が不足しています。X_AUTH_STATE または X_USERNAME/X_PASSWORD を設定してください');
  }

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
    const contextOptions = {
      locale: 'ja-JP',
      viewport: { width: 1280, height: 900 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    };

    if (statePath && existsSync(statePath)) {
      console.log(`✓ 保存済みX認証状態を使用: ${statePath}`);
      contextOptions.storageState = statePath;
    }

    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();
    page.setDefaultTimeout(30000);

    await page.goto(COMPOSE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    await ensureLoggedIn(page, context, { loginId, password, handle, statePath });

    const textbox = page.locator('[data-testid="tweetTextarea_0"], div[role="textbox"][contenteditable="true"]').first();
    await textbox.waitFor({ state: 'visible', timeout: 30000 });
    await textbox.click({ force: true });
    await page.keyboard.type(tweetText, { delay: 15 });

    const postButton = page.locator('[data-testid="tweetButtonInline"], [data-testid="tweetButton"]').first();
    await postButton.waitFor({ state: 'visible', timeout: 15000 });

    for (let i = 0; i < 20; i++) {
      if (await postButton.isEnabled()) break;
      await page.waitForTimeout(200);
    }

    await postButton.click();
    await page.waitForTimeout(5000);

    console.log('✅ X投稿成功 (Playwright)');
    if (handle) {
      console.log(`🔗 想定プロフィールURL: https://x.com/${handle}`);
    }
  } catch (error) {
    const errorPath = path.join(os.tmpdir(), `x-post-error-${Date.now()}.png`);
    try {
      const pages = browser.contexts().flatMap(ctx => ctx.pages());
      const activePage = pages[pages.length - 1];
      if (activePage) {
        await activePage.screenshot({ path: errorPath, fullPage: true });
        console.log(`📷 X投稿エラースクリーンショット: ${errorPath}`);
      }
    } catch {
      // ignore screenshot failure
    }
    throw error;
  } finally {
    await browser.close();
  }
}

async function ensureLoggedIn(page, context, { loginId, password, handle, statePath }) {
  const composeReady = await isComposeReady(page);
  if (composeReady) {
    return;
  }

  if (!loginId || !password) {
    throw new Error('Xへのログインが必要ですが、X_USERNAME/X_PASSWORD がありません');
  }

  console.log('🔐 Xへ自動ログイン中...');
  await page.goto('https://x.com/i/flow/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  const textInput = page.locator('input[autocomplete="username"], input[name="text"]').first();
  await textInput.waitFor({ state: 'visible', timeout: 30000 });
  await textInput.fill(loginId);
  await clickMatchingButton(page, ['Next', '次へ']);
  await page.waitForTimeout(3000);

  const passwordInput = page.locator('input[name="password"]').first();
  if (!(await passwordInput.isVisible().catch(() => false))) {
    const challengeInput = page.locator('input[name="text"]').first();
    if (await challengeInput.isVisible().catch(() => false)) {
      await challengeInput.fill(handle || loginId);
      await clickMatchingButton(page, ['Next', '次へ']);
      await page.waitForTimeout(3000);
    }
  }

  await passwordInput.waitFor({ state: 'visible', timeout: 30000 });
  await passwordInput.fill(password);
  await clickMatchingButton(page, ['Log in', 'ログイン']);
  await page.waitForTimeout(5000);

  if (statePath) {
    const storageState = await context.storageState();
    writeFileSync(statePath, JSON.stringify(storageState, null, 2));
    console.log(`✓ X認証状態を保存: ${statePath}`);
  }

  await page.goto(COMPOSE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  if (!(await isComposeReady(page))) {
    throw new Error(`Xの投稿画面に到達できませんでした: ${page.url()}`);
  }
}

async function clickMatchingButton(page, labels) {
  for (const label of labels) {
    const button = page.locator(`button:has-text("${label}")`).first();
    if (await button.isVisible().catch(() => false)) {
      await button.click();
      return;
    }
  }
  await page.keyboard.press('Enter');
}

async function isComposeReady(page) {
  const textbox = page.locator('[data-testid="tweetTextarea_0"], div[role="textbox"][contenteditable="true"]').first();
  return await textbox.isVisible().catch(() => false);
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const positional = args.filter(arg => arg !== '--dry-run');

  if (positional.length < 2) {
    console.error('使用方法: node post_to_x.js <article.md> <note_url> [--dry-run]');
    process.exit(1);
  }

  const [articlePath, noteUrl] = positional;
  await postToX({ articlePath, noteUrl, dryRun });
}

main().catch(error => {
  console.error('❌ X投稿失敗:', error.message);
  process.exit(1);
});
