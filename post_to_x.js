import { readFileSync } from 'fs';
import path from 'path';
import { TwitterApi } from 'twitter-api-v2';

const MAX_TWEET_LENGTH = 270;

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

  const {
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_TOKEN_SECRET,
  } = process.env;

  if (!X_API_KEY || !X_API_SECRET || !X_ACCESS_TOKEN || !X_ACCESS_TOKEN_SECRET) {
    throw new Error('X API用の環境変数が不足しています');
  }

  const client = new TwitterApi({
    appKey: X_API_KEY,
    appSecret: X_API_SECRET,
    accessToken: X_ACCESS_TOKEN,
    accessSecret: X_ACCESS_TOKEN_SECRET,
  });

  const result = await client.v2.tweet(tweetText);
  console.log(`✅ X投稿成功: tweet_id=${result.data.id}`);
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
