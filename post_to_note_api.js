#!/usr/bin/env node
/**
 * note.com 内部 API へ HTTP で投稿（非公式・自己責任）
 *
 * create が 422 になる主な要因:
 * - XSRF / CSRF が editor セッションと一致していない
 * - ペイロード形式が JSON:API に寄っている
 *
 * 対策: editor.note.com/new を GET して Cookie マージ + meta csrf-token を取得し、
 *      複数 URL / ペイロードで create を試行 → draft_save。
 */

import { readFileSync, existsSync } from 'fs';
import { marked } from 'marked';

const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

function parseMarkdown(content) {
  const lines = content.split('\n');
  let title = '';
  let body = '';
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

/** Set-Cookie を既存 Cookie 行にマージ（Node 18+ fetch） */
function mergeCookiesFromResponse(cookieHeader, response) {
  if (!response?.headers?.getSetCookie) return cookieHeader;
  const setCookies = response.headers.getSetCookie();
  if (!setCookies?.length) return cookieHeader;
  const map = new Map();
  for (const part of cookieHeader.split(';')) {
    const t = part.trim();
    if (!t) continue;
    const eq = t.indexOf('=');
    if (eq > 0) map.set(t.slice(0, eq).trim(), t.slice(eq + 1).trim());
  }
  for (const sc of setCookies) {
    const pair = sc.split(';')[0];
    const eq = pair.indexOf('=');
    if (eq > 0) map.set(pair.slice(0, eq).trim(), pair.slice(eq + 1).trim());
  }
  return [...map.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
}

/** editor を開いて Cookie 更新 + HTML から csrf-token を抽出 */
async function warmupEditorSession(cookieHeader) {
  let cookies = cookieHeader;
  let csrfMeta = null;

  for (const url of ['https://editor.note.com/new', 'https://note.com/']) {
    try {
      const res = await fetch(url, {
        redirect: 'follow',
        headers: {
          'User-Agent': UA,
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'ja,en-US;q=0.9',
          Cookie: cookies,
        },
      });
      cookies = mergeCookiesFromResponse(cookies, res);
      const html = await res.text();
      const m =
        html.match(/name="csrf-token"\s+content="([^"]+)"/) ||
        html.match(/content="([^"]+)"\s+name="csrf-token"/) ||
        html.match(/csrf-token"\s+content="([^"]+)"/);
      if (m) csrfMeta = m[1];
    } catch {
      /* continue */
    }
  }

  return { cookies, csrfMeta };
}

function buildHeaders(cookieHeader, extra = {}) {
  const xsrf = extractXsrfToken(cookieHeader);
  const h = {
    'User-Agent': UA,
    Accept: 'application/json, text/plain, */*',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    Cookie: cookieHeader,
    Origin: 'https://note.com',
    Referer: 'https://editor.note.com/new',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    ...extra,
  };
  if (xsrf) {
    h['X-XSRF-TOKEN'] = xsrf;
    h['X-Requested-With'] = 'XMLHttpRequest';
  }
  return h;
}

async function postJson(url, cookieHeader, payload, contentType, extraHeaders = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      ...buildHeaders(cookieHeader, extraHeaders),
      'Content-Type': contentType || 'application/json',
    },
    body: typeof payload === 'string' ? payload : JSON.stringify(payload),
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

function extractNoteIdAndKey(j) {
  if (!j) return { id: null, key: null };
  const d = j.data;
  if (d && typeof d === 'object' && !Array.isArray(d)) {
    const id = d.id != null ? String(d.id) : null;
    const key =
      d.attributes?.key ||
      d.attributes?.note_key ||
      d.key ||
      null;
    return { id, key: key || null };
  }
  return {
    id: j.text_note?.id != null ? String(j.text_note.id) : j.id != null ? String(j.id) : null,
    key: j.text_note?.key || j.key || null,
  };
}

async function createAndSaveNote(cookieHeader, title, html, wantPublish) {
  console.log('🔐 editor セッションをウォームアップ（Cookie / CSRF）…');
  const { cookies, csrfMeta } = await warmupEditorSession(cookieHeader);
  const session = cookies;
  if (csrfMeta) {
    console.log('   ✓ csrf-token (meta) を取得');
  }

  const extraCsrf = csrfMeta ? { 'X-CSRF-Token': csrfMeta } : {};

  // Step 1: create（複数試行）
  const step1 = await (async () => {
    const urls = [
      'https://note.com/api/v1/text_notes',
      'https://editor.note.com/api/v1/text_notes',
    ];
    const shortTitle = [...title].slice(0, 200).join('');
    const tinyBody = '<p><br></p>';
    const variants = [
      { ct: 'application/json', payload: { name: shortTitle, body: tinyBody } },
      { ct: 'application/json', payload: { name: shortTitle, body: html } },
      {
        ct: 'application/vnd.api+json',
        payload: {
          data: { type: 'text_notes', attributes: { name: shortTitle, body: tinyBody } },
        },
      },
      {
        ct: 'application/vnd.api+json',
        payload: {
          data: { type: 'text_notes', attributes: { name: shortTitle, body: html } },
        },
      },
      {
        ct: 'application/vnd.api+json',
        payload: {
          data: { type: 'textNotes', attributes: { name: shortTitle, body: tinyBody } },
        },
      },
      { ct: 'application/json', payload: { text_note: { name: shortTitle, body: tinyBody } } },
      { ct: 'application/json', payload: { text_note: { name: shortTitle, body: html } } },
      ...(csrfMeta
        ? [
            {
              ct: 'application/json',
              payload: { name: shortTitle, body: tinyBody, authenticity_token: csrfMeta },
            },
          ]
        : []),
    ];

    let last = { ok: false, status: 0, raw: '', json: null };
    for (const baseUrl of urls) {
      for (let i = 0; i < variants.length; i++) {
        const v = variants[i];
        const r = await postJson(baseUrl, session, v.payload, v.ct, extraCsrf);
        last = r;
        if (r.ok) {
          console.log(`   ✓ create 成功: ${baseUrl} (試行 ${i + 1})`);
          return r;
        }
      }
    }
    return { ok: false, status: last.status, raw: last.raw, json: last.json };
  })();

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

  const base = 'https://note.com/api/v1/text_notes';
  const bodyLength = [...html].length;

  const draftUrl = `${base}/draft_save?id=${encodeURIComponent(noteId)}&is_temp_saved=true`;
  const step2 = await postJson(
    draftUrl,
    session,
    {
      name: title,
      body: html,
      body_length: bodyLength,
      index: false,
      is_lead_form: false,
    },
    'application/json',
    extraCsrf
  );

  if (!step2.ok) {
    const draftUrlEd = `https://editor.note.com/api/v1/text_notes/draft_save?id=${encodeURIComponent(noteId)}&is_temp_saved=true`;
    const step2b = await postJson(
      draftUrlEd,
      session,
      {
        name: title,
        body: html,
        body_length: bodyLength,
        index: false,
        is_lead_form: false,
      },
      'application/json',
      extraCsrf
    );
    if (!step2b.ok) {
      return {
        ok: false,
        phase: 'draft_save',
        status: step2.status,
        raw: step2.raw,
        json: step2.json,
        noteId,
      };
    }
    Object.assign(step2, step2b);
  }

  const afterDraft = extractNoteIdAndKey(step2.json);
  if (afterDraft.key) noteKey = afterDraft.key;
  if (afterDraft.id) noteId = afterDraft.id;

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
          ...buildHeaders(session, extraCsrf),
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
      console.log(`⚠️  公開API試行失敗 (${pub.status}): ${pUrl.slice(0, 88)}`);
    }
    console.log('⚠️  自動公開APIが使えませんでした。下書きは保存済みの可能性があります。');
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
    return `<p><em>[画像: ${src}]</em></p>`;
  });

  console.log('📮 note API 投稿（ウォームアップ + 複数 create 試行）');
  console.log(`   タイトル: ${title}`);
  console.log(`   モード: ${wantPublish ? '公開' : '下書き'}`);
  console.log('');

  const result = await createAndSaveNote(cookieHeader, title, html, wantPublish);

  if (!result.ok) {
    console.error('❌ API 投稿に失敗しました');
    console.error(`   フェーズ: ${result.phase}`);
    console.error(`   HTTP ${result.status}`);
    console.error('   レスポンス:', (result.raw || '').slice(0, 2000));
    console.error('');
    console.error('💡 GitHub Secret の NOTE_SESSION_COOKIE を取り直してください:');
    console.error('   1) ブラウザで https://editor.note.com/new を開いた状態でログイン済みであること');
    console.error('   2) npm run note:cookie または DevTools → Application → Cookies（note.com / editor）');
    console.error('   3) note_session と XSRF-TOKEN が同じブラウザセッションのものであること');
    process.exit(1);
  }

  const noteUrl = extractNoteUrl(result);
  console.log('✅ 処理完了');
  if (result.publishSkipped) {
    console.log('⚠️  自動公開はスキップされた可能性 → 下書きを確認して手動公開してください。');
  }
  if (result.json) {
    console.log(JSON.stringify(result.json, null, 2).slice(0, 1500));
  }
  if (noteUrl) {
    console.log(`NOTE_ARTICLE_URL=${noteUrl}`);
  } else {
    console.log('⚠️  NOTE_ARTICLE_URL を自動抽出できませんでした。マイページで確認してください。');
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
