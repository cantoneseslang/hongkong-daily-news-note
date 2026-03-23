#!/usr/bin/env node
/**
 * note.com 内部 API へ HTTP で投稿（ブラウザ自動ログイン不要）
 *
 * 仕様（非公式・変更の可能性あり）:
 * - 1) POST /api/v1/text_notes に { name, body } のみ（status は付けない）→ 422 回避
 * - 2) POST /api/v1/text_notes/draft_save?id=...&is_temp_saved=... に本文＋メタデータ
 * - 3) 公開時は /api/v2/notes/{key}/publish 等を試行（key はレスポンスから取得）
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

async function postJson(url, cookieHeader, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      ...buildHeaders(cookieHeader),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    /* raw */
  }
  return { ok: res.ok, status: res.status, json, raw: text };
}

/** JSON:API / 旧形式の両方から id / key を取る */
function extractNoteIdAndKey(j) {
  if (!j) return { id: null, key: null };
  const d = j.data;
  if (d && typeof d === 'object') {
    const id = d.id != null ? String(d.id) : null;
    const key =
      d.attributes?.key ||
      d.attributes?.note_key ||
      d.key ||
      (typeof d.attributes === 'object' && d.attributes?.slug) ||
      null;
    return { id, key: key || null };
  }
  return {
    id: j.text_note?.id != null ? String(j.text_note.id) : j.id != null ? String(j.id) : null,
    key: j.text_note?.key || j.key || null,
  };
}

/**
 * 2段階投稿（参考: note 非公式API調査記事）+ 公開用エンドポイントの試行
 */
async function createAndSaveNote(cookieHeader, title, html, wantPublish) {
  const base = 'https://note.com/api/v1/text_notes';

  // Step 1: status を付けない（付けると 422 になりやすい）
  const step1 = await postJson(base, cookieHeader, {
    name: title,
    body: html,
  });

  if (!step1.ok) {
    return {
      ok: false,
      phase: 'create',
      status: step1.status,
      raw: step1.raw,
      json: step1.json,
    };
  }

  let { id: noteId, key: noteKey } = extractNoteIdAndKey(step1.json);
  if (!noteId) {
    return {
      ok: false,
      phase: 'parse_id',
      status: step1.status,
      raw: step1.raw,
      json: step1.json,
    };
  }

  const bodyLength = [...html].length;

  // Step 2: draft_save（本文確定）— 調査記事どおり is_temp_saved=true
  const draftUrl = `${base}/draft_save?id=${encodeURIComponent(noteId)}&is_temp_saved=true`;
  const step2 = await postJson(draftUrl, cookieHeader, {
    name: title,
    body: html,
    body_length: bodyLength,
    index: false,
    is_lead_form: false,
  });

  if (!step2.ok) {
    return {
      ok: false,
      phase: 'draft_save',
      status: step2.status,
      raw: step2.raw,
      json: step2.json,
      noteId,
    };
  }

  const afterDraft = extractNoteIdAndKey(step2.json);
  if (afterDraft.key) noteKey = afterDraft.key;
  if (afterDraft.id) noteId = afterDraft.id;

  // Step 3: 公開（下書きでなければ複数パターンを試す）
  if (wantPublish) {
    const publishAttempts = [];
    if (noteKey && /^n[a-f0-9]+$/i.test(noteKey)) {
      publishAttempts.push(`https://note.com/api/v2/notes/${encodeURIComponent(noteKey)}/publish`);
    }
    publishAttempts.push(`${base}/open_publish?id=${encodeURIComponent(noteId)}`);

    for (const pUrl of publishAttempts) {
      const pub = await fetch(pUrl, {
        method: 'POST',
        headers: {
          ...buildHeaders(cookieHeader),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });
      const pubText = await pub.text();
      let pubJson = null;
      try {
        pubJson = JSON.parse(pubText);
      } catch {
        /* ignore */
      }
      if (pub.ok) {
        return {
          ok: true,
          json: pubJson || step2.json,
          raw: pubText,
          noteId,
          noteKey: noteKey || extractNoteIdAndKey(pubJson).key,
        };
      }
      console.log(`⚠️  公開API試行失敗 (${pub.status}): ${pUrl.slice(0, 80)}…`);
    }
    // 公開APIが全部失敗しても下書きまではできている → 警告付き成功扱いにするか判断
    console.log('⚠️  自動公開APIが使えませんでした。下書きまで保存済みの可能性があります。note で手動公開してください。');
    return {
      ok: true,
      json: step2.json,
      raw: step2.raw,
      noteId,
      noteKey,
      publishSkipped: true,
    };
  }

  return {
    ok: true,
    json: step2.json,
    raw: step2.raw,
    noteId,
    noteKey,
  };
}

function extractNoteUrl(result) {
  const j = result.json;
  if (!j) return null;
  const key =
    result.noteKey ||
    j?.data?.attributes?.key ||
    j?.data?.key ||
    j?.data?.attributes?.note_key ||
    j?.key ||
    j?.text_note?.key;
  if (key && typeof key === 'string' && key.length > 3) {
    return `https://note.com/n/${key}`;
  }
  return null;
}

async function main() {
  const mdPath = process.argv[2];
  const mode = (process.argv[3] || '公開').toLowerCase();
  const wantPublish = !mode.includes('下書');

  const cookieHeader = process.env.NOTE_SESSION_COOKIE?.trim();
  if (!cookieHeader) {
    console.error('❌ 環境変数 NOTE_SESSION_COOKIE が空です。');
    console.error('   ブラウザでログイン後、Request Cookie ヘッダを Secret に保存してください。');
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

  html = html.replace(/<img[^>]+src="([^"]+)"/g, (match, src) => {
    if (src.startsWith('http')) return match;
    return `<p><em>[画像: ${src} — API投稿では手動アップロードが必要な場合があります]</em></p>`;
  });

  console.log('📮 note API 投稿（HTTP・2段階）');
  console.log(`   タイトル: ${title}`);
  console.log(`   モード: ${wantPublish ? '公開（可能なら自動公開API）' : '下書き'}`);
  console.log('');

  const result = await createAndSaveNote(cookieHeader, title, html, wantPublish);

  if (!result.ok) {
    console.error('❌ API 投稿に失敗しました');
    console.error(`   フェーズ: ${result.phase}`);
    console.error(`   HTTP ${result.status}`);
    console.error('   レスポンス:', (result.raw || '').slice(0, 2000));
    console.error('');
    console.error('💡 Cookie に XSRF-TOKEN が含まれているか確認（editor.note.com で取得した Cookie 推奨）');
    console.error('💡 非公式 API の仕様変更の可能性もあります。');
    process.exit(1);
  }

  const noteUrl = extractNoteUrl(result);
  console.log('✅ 下書き保存まで成功した可能性が高いです。');
  if (result.publishSkipped) {
    console.log('⚠️  自動公開は未実施の可能性 → マイページで下書きを確認し、必要なら手動で公開してください。');
  }
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
