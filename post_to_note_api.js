#!/usr/bin/env node
/**
 * note.com 内部 API へ HTTP で投稿（非公式・自己責任）
 *
 * - API POST は https://note.com/api/... のみ（editor ホストは CloudFront 403 になりやすい）
 * - ウォームアップ GET が Set-Cookie でセッションを壊すことがあるため、
 *   まず「Secret の Cookie をそのまま」で create を試し、ダメならだけウォームアップ後に再試行
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

async function warmupEditorSession(cookieHeader) {
  let cookies = cookieHeader;
  let csrfMeta = null;

  for (const url of ['https://note.com/', 'https://note.com/login']) {
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

/** Rails 系で form POST を受け付ける場合がある */
async function postForm(url, cookieHeader, fields, extraHeaders = {}) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(fields)) {
    if (v != null) params.append(k, String(v));
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      ...buildHeaders(cookieHeader, extraHeaders),
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    },
    body: params.toString(),
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

const CREATE_URL = 'https://note.com/api/v1/text_notes';

/**
 * create を総当たり。extraHeaders で Origin を差し替え（ブラウザのエディタ起点を真似る）
 */
async function attemptCreate(session, shortTitle, html, csrfMeta) {
  const tinyBody = '<p><br></p>';
  const extraCsrf = csrfMeta ? { 'X-CSRF-Token': csrfMeta } : {};

  const originOverrides = [
    {},
    { Origin: 'https://editor.note.com', Referer: 'https://editor.note.com/new' },
    { Origin: 'https://note.com', Referer: 'https://note.com/' },
  ];

  const jsonVariants = [
    { ct: 'application/json', payload: { name: shortTitle, body: tinyBody } },
    { ct: 'application/json', payload: { name: shortTitle, body: html } },
    { ct: 'application/json', payload: { name: shortTitle, body: tinyBody, format: 'html' } },
    { ct: 'application/json', payload: { text_note: { name: shortTitle, body: tinyBody } } },
    {
      ct: 'application/vnd.api+json',
      payload: {
        data: { type: 'text_notes', attributes: { name: shortTitle, body: tinyBody } },
      },
    },
    ...(csrfMeta
      ? [{ ct: 'application/json', payload: { name: shortTitle, body: tinyBody, authenticity_token: csrfMeta } }]
      : []),
  ];

  let last = { ok: false, status: 0, raw: '', json: null };

  for (const originExtra of originOverrides) {
    const merged = { ...extraCsrf, ...originExtra };
    for (let i = 0; i < jsonVariants.length; i++) {
      const v = jsonVariants[i];
      const r = await postJson(CREATE_URL, session, v.payload, v.ct, merged);
      last = r;
      if (r.ok) {
        console.log(`   ✓ create 成功 (JSON 試行 ${i + 1}, Origin=${originExtra.Origin || 'note.com'})`);
        return r;
      }
    }
    const formR = await postForm(
      CREATE_URL,
      session,
      { name: shortTitle, body: tinyBody },
      merged
    );
    last = formR;
    if (formR.ok) {
      console.log('   ✓ create 成功 (form-urlencoded)');
      return formR;
    }
  }

  return { ok: false, status: last.status, raw: last.raw, json: last.json };
}

function envTruthy(name) {
  const v = process.env[name];
  if (v == null || v === '') return false;
  return v === '1' || /^true$/i.test(v);
}

async function createAndSaveNote(cookieHeader, title, html, wantPublish) {
  const shortTitle = [...title].slice(0, 200).join('');
  const skipWarmup = envTruthy('NOTE_API_SKIP_WARMUP');

  if (skipWarmup) {
    console.log('🔐 NOTE_API_SKIP_WARMUP → ウォームアップをスキップ（生 Cookie のみで create）');
  }

  /** create に成功したときの Cookie（draft / publish でも同じものを使う） */
  let sess = cookieHeader;
  /** ウォームアップで取れた meta csrf（あれば draft に付与） */
  let csrfMeta = null;

  let step1 = await attemptCreate(sess, shortTitle, html, null);

  if (!step1.ok && !skipWarmup) {
    console.log('🔐 生 Cookie で失敗 → ウォームアップ後に再試行…');
    const w = await warmupEditorSession(cookieHeader);
    sess = w.cookies;
    csrfMeta = w.csrfMeta;
    if (csrfMeta) console.log('   ✓ csrf-token (meta) を取得');
    step1 = await attemptCreate(sess, shortTitle, html, csrfMeta);
  }

  if (!step1.ok) {
    return {
      ok: false,
      phase: 'create',
      status: step1.status,
      raw: step1.raw,
      json: step1.json,
    };
  }

  const extraCsrf = csrfMeta ? { 'X-CSRF-Token': csrfMeta } : {};

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

  async function doDraft(cookieStr) {
    return postJson(
      draftUrl,
      cookieStr,
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
  }

  /** create が通った Cookie を最優先。失敗時のみ別 Cookie を試す */
  let step2 = await doDraft(sess);
  if (!step2.ok) {
    step2 = await doDraft(cookieHeader);
  }

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
          ...buildHeaders(sess, extraCsrf),
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

function isCloudFrontBlocked(raw) {
  return typeof raw === 'string' && raw.includes('CloudFront') && (raw.includes('403') || raw.includes('ERROR'));
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

  console.log('📮 note API 投稿（生 Cookie 優先 → 必要ならウォームアップ）');
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
    if (result.status === 403 && isCloudFrontBlocked(result.raw)) {
      console.error('💡 CloudFront 403: GitHub Actions 等の IP からの POST がブロックされている可能性があります。');
      console.error('   Variables: SKIP_NOTE_POST=true で投稿のみスキップ、など。');
      console.error('');
    }
    if (result.status === 422) {
      console.error('💡 422 のとき:');
      console.error('   · Repository Variables に NOTE_API_SKIP_WARMUP=true を設定（ウォームアップで Cookie が壊れるのを防ぐ）');
      console.error('   · 手元で NOTE_SESSION_COOKIE=... node post_to_note_api.js ... が通るか確認');
      console.error('   · note の仕様変更で API だけでは投稿できない可能性 → SKIP_NOTE_POST + 手動投稿');
      console.error('');
    }
    console.error('💡 Cookie を取り直す: npm run note:cookie → .note-session-cookie.txt を Secret に');
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
