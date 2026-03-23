#!/usr/bin/env node
/**
 * note.com 内部 API へ HTTP で投稿（ブラウザ自動ログイン不要）
 *
 * 前提: 普段のブラウザで note にログインした状態の Cookie を取得し、
 *       GitHub Secret「NOTE_SESSION_COOKIE」に保存する。
 *
 * 取得手順（Chrome）:
 *   1. https://note.com にログイン
 *   2. DevTools → Application → Cookies → https://note.com
 *   3. note_session（および XSRF-TOKEN 等がある場合は同じ画面の Cookie をまとめて）
 *   または Network タブで note.com へのリクエスト → Request Headers の Cookie 行をコピー
 *
 * 非公式 API のため、仕様変更で動かなくなる可能性があります（自己責任）。
 *
 * Usage:
 *   NOTE_SESSION_COOKIE="..." node post_to_note_api.js <記事.md> [公開|下書き]
 */

import { readFileSync, existsSync } from 'fs';
import { marked } from 'marked';
import * as path from 'path';

const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

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
          tags.push(...tagsStr.slice(1, -1).split(',').map((t) => t.trim().replace(/^["']|["']$/g, '')));
        }
      } else if (line.trim().startsWith('-')) {
        const tag = line.trim().substring(1).trim().replace(/^["']|["']$/g, '');
        if (tag) tags.push(tag);
      }
      continue;
    }

    if (!titleFound && line.startsWith('# ')) {
      if (!title) {
        title = line.substring(2).trim();
      }
      titleFound = true;
      continue;
    }

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

/** Cookie 文字列から XSRF-TOKEN を取り出す（あれば） */
function extractXsrfToken(cookieHeader) {
  const m = cookieHeader.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/i);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1].trim());
  } catch {
    return m[1].trim();
  }
}

function buildHeaders(cookieHeader, extra = {}) {
  const h = {
    'User-Agent': UA,
    Accept: 'application/json, text/plain, */*',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    Cookie: cookieHeader,
    Origin: 'https://note.com',
    Referer: 'https://editor.note.com/new',
    ...extra,
  };
  const xsrf = extractXsrfToken(cookieHeader);
  if (xsrf) {
    h['X-XSRF-TOKEN'] = xsrf;
    h['X-Requested-With'] = 'XMLHttpRequest';
  }
  return h;
}

async function tryCreateNote(cookieHeader, title, html, status) {
  const payloads = [
    { name: title, body: html, status },
    { text_note: { name: title, body: html, status } },
    {
      data: {
        type: 'textNotes',
        attributes: { name: title, body: html, status },
      },
    },
  ];

  const url = 'https://note.com/api/v1/text_notes';

  for (let i = 0; i < payloads.length; i++) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        ...buildHeaders(cookieHeader),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payloads[i]),
    });
    const text = await res.text();
    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      /* raw */
    }

    if (res.ok) {
      return { ok: true, json, raw: text, variant: i };
    }

    if (i === payloads.length - 1) {
      return { ok: false, status: res.status, json, raw: text, variant: i };
    }
    console.log(`⚠️  投稿パターン ${i + 1} 失敗 (${res.status})。別形式を試します…`);
  }
  return { ok: false, status: 0, raw: 'no payload' };
}

function extractNoteUrl(result) {
  const j = result.json;
  if (!j) return null;
  const key =
    j?.data?.key ||
    j?.data?.attributes?.key ||
    j?.key ||
    j?.text_note?.key ||
    j?.data?.id ||
    j?.id;
  if (key && typeof key === 'string' && key.length > 5) {
    return `https://note.com/n/${key}`;
  }
  return null;
}

async function main() {
  const mdPath = process.argv[2];
  const mode = (process.argv[3] || '公開').toLowerCase();
  const status = mode.includes('下書') ? 'draft' : 'published';

  const cookieHeader = process.env.NOTE_SESSION_COOKIE?.trim();
  if (!cookieHeader) {
    console.error('❌ 環境変数 NOTE_SESSION_COOKIE が空です。');
    console.error('   ブラウザでログイン後、DevTools の Cookie または Request Cookie ヘッダを Secret に保存してください。');
    process.exit(1);
  }

  if (!mdPath || !existsSync(mdPath)) {
    console.error('使い方: NOTE_SESSION_COOKIE="..." node post_to_note_api.js <記事.md> [公開|下書き]');
    process.exit(1);
  }

  const mdContent = readFileSync(mdPath, 'utf-8');
  const { title, body } = parseMarkdown(mdContent);

  marked.setOptions({ gfm: true, breaks: true });
  let html = marked.parse(body);

  // ローカル画像パスは note 側で表示できないため、説明に差し替え
  html = html.replace(/<img[^>]+src="([^"]+)"/g, (match, src) => {
    if (src.startsWith('http')) return match;
    return `<p><em>[画像: ${src} — API投稿では手動アップロードが必要な場合があります]</em></p>`;
  });

  console.log('📮 note API 投稿（HTTP）');
  console.log(`   タイトル: ${title}`);
  console.log(`   ステータス: ${status}`);
  console.log('');

  const result = await tryCreateNote(cookieHeader, title, html, status);

  if (!result.ok) {
    console.error('❌ API 投稿に失敗しました');
    console.error(`   HTTP ${result.status}`);
    console.error('   レスポンス:', (result.raw || '').slice(0, 2000));
    console.error('');
    console.error('💡 確認: NOTE_SESSION_COOKIE が最新か、note にログインできるブラウザからコピーしたか');
    console.error('💡 非公式 API の仕様変更の可能性もあります。');
    process.exit(1);
  }

  const noteUrl = extractNoteUrl(result);
  console.log('✅ 投稿に成功した可能性が高いです（レスポンスを確認してください）');
  if (result.json) {
    console.log(JSON.stringify(result.json, null, 2).slice(0, 1500));
  }
  if (noteUrl) {
    console.log(`NOTE_ARTICLE_URL=${noteUrl}`);
  } else {
    console.log('⚠️  記事 URL を自動抽出できませんでした。note のマイページで確認してください。');
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
