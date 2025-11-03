#!/usr/bin/env python3
import sys
import re
from pathlib import Path


def count_kana(text: str) -> int:
    return len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF]", text))


def remove_invalid_weather_section(markdown: str) -> str:
    # Locate weather block
    weather_header = "## 本日の香港の天気"
    start = markdown.find(weather_header)
    if start == -1:
        # Fallback: try block starting at '### 天気予報' before the first news section
        first_h3 = re.search(r"\n### ", markdown)
        if not first_h3:
            return markdown
        # Check if that first h3 is 天気予報
        # Find the line start
        h3_start = first_h3.start() + 1  # skip leading newline
        line_end = markdown.find('\n', h3_start)
        line = markdown[h3_start: line_end if line_end != -1 else len(markdown)]
        if not line.startswith('### 天気予報'):
            return markdown
        # Define weather block as from this h3 to the next h3 occurrence
        remainder = markdown[line_end if line_end != -1 else h3_start:]
        matches = list(re.finditer(r"\n### ", remainder))
        if len(matches) >= 1:
            end = (line_end if line_end != -1 else h3_start) + matches[0].start()
        else:
            end = len(markdown)
        start = h3_start - 1  # include the newline before ###
        weather_block = markdown[start:end]
        content_only = weather_block.replace('天気予報', '').replace('引用元', '').replace('香港天文台', '')
        has_error_tag = "[翻訳エラー" in weather_block
        kana_ok = count_kana(content_only) >= 11
        if has_error_tag or not kana_ok:
            before = markdown[:start].rstrip()
            after = markdown[end:]
            after = re.sub(r"^\n+", "\n\n", after)
            return before + "\n\n" + after.lstrip('\n')
        return markdown

    # Find the second '### ' occurrence after the weather header:
    # 1st is '### 天気予報', 2nd is the first news section
    remainder = markdown[start + len(weather_header):]
    matches = list(re.finditer(r"\n### ", remainder))
    if len(matches) >= 2:
        end = start + len(weather_header) + matches[1].start()
    else:
        end = len(markdown)

    weather_block = markdown[start:end]

    # Validation: no explicit error tag, and sufficient kana content
    block_for_lang_check = re.sub(r"[\s\n]*", "", weather_block)
    has_error_tag = "[翻訳エラー" in weather_block

    # Exclude Japanese labels from kana count
    content_only = weather_block
    for marker in ["本日の香港の天気", "天気予報", "引用元", "香港天文台"]:
        content_only = content_only.replace(marker, "")
    kana_ok = count_kana(content_only) >= 11

    if has_error_tag or not kana_ok:
        # Remove the entire weather block including trailing blank lines
        before = markdown[:start].rstrip()
        after = markdown[end:]
        # Ensure no extra leading blank lines remain before the next section
        after = re.sub(r"^\n+", "\n\n", after)
        return before + "\n\n" + after.lstrip('\n')

    return markdown


def normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def title_similarity(a: str, b: str) -> float:
    # Robust similarity for non-spaced languages (Japanese): use SequenceMatcher ratio
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def normalize_url(url: str) -> str:
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, '', '', ''))
    except Exception:
        return url


def dedup_sections(markdown: str, sim_threshold: float = 0.9):
    # Split into lines and locate sections starting with '### '
    sections = re.split(r"\n### ", markdown)
    if len(sections) <= 1:
        return markdown

    # Keep preface (before first section)
    preface = sections[0]
    rest = sections[1:]

    kept = []
    seen_titles = []
    seen_urls = set()

    for sec in rest:
        # Reattach header marker
        block = "### " + sec
        # Title-only check for HK markers
        first_nl = sec.find('\n')
        title_text = (sec[:first_nl] if first_nl != -1 else sec).strip()
        title_l = title_text.lower()
        # Title-only check for HK markers
        first_nl = sec.find('\n')
        title_text = (sec[:first_nl] if first_nl != -1 else sec).strip()
        title_l = title_text.lower()
        # Extract title (first line after '### ')
        lines = sec.split('\n')
        title = lines[0].strip() if lines else ""
        norm_title = normalize_title(title)

        # Extract first URL in the section (independent line)
        url_match = re.search(r"(?m)^(https?://\S+)$", block)
        norm_url = normalize_url(url_match.group(1)) if url_match else None

        # URL-based dedup
        if norm_url and norm_url in seen_urls:
            continue

        # Title fuzzy dedup
        is_dup = False
        for st in seen_titles:
            if title_similarity(norm_title, st) >= sim_threshold:
                is_dup = True
                break

        if is_dup:
            continue

        kept.append(block)
        seen_titles.append(norm_title)
        if norm_url:
            seen_urls.add(norm_url)

    result = preface.rstrip() + ("\n\n" if preface and kept else "") + "\n\n".join(k.strip() for k in kept)
    return result.strip() + "\n"


def filter_non_hk_sections(markdown: str) -> str:
    """Remove sections that are not clearly Hong Kong/GBA related.

    Heuristics:
    - Keep if section text contains HK/GBA markers (JA/EN/ZH)
    - Keep if URL path contains /hong-kong, /hongkong, /greater-bay-area, /gba/
    - SCMP must have /hong-kong* in path
    - Drop Google News relay URLs unless text has HK markers
    """
    hk_markers = [
        'hong kong', 'hongkong', '香港', '九龍', '新界', '中環', '尖沙咀', '灣仔', '旺角',
        'hksar', '香港天文台', '港鐵', 'mtr', 'hkex', '香港交易所'
    ]
    gba_markers = [
        'greater bay area', 'gba', '粵港澳大灣區', '粤港澳大湾区', '大湾区', '珠三角',
        '深圳', '深セン', '东莞', '東莞', '广州', '広州', '珠海', '佛山', '惠州', '中山', '江門', '江门', '肇慶', '肇庆',
        'shenzhen', 'dongguan', 'guangzhou', 'foshan', 'zhuhai', 'huizhou', 'zhongshan', 'jiangmen', 'zhaoqing'
    ]

    import re
    from urllib.parse import urlparse

    parts = re.split(r"\n### ", markdown)
    if len(parts) <= 1:
        return markdown

    preface = parts[0]
    rest = parts[1:]
    kept = []

    for sec in rest:
        block = "### " + sec
        # Title-only check for HK markers (compute once)
        _first_nl = sec.find('\n')
        _title_text = (sec[:_first_nl] if _first_nl != -1 else sec).strip()
        # Ignore trailing source suffix like " - Techritual 香港" or separators like "｜"
        import re as _re
        _title_core = _re.split(r"\s[-|｜]\s", _title_text)[0]
        title_l = _title_core.lower()
        # Use only the narrative part before citation for HK marker checks
        citation_idx = block.find("**引用元**:")
        narrative = block[:citation_idx] if citation_idx != -1 else block
        # Remove font-labelled source hints and HTML tags to avoid false HK hits
        narrative = re.sub(r"<font[^>]*>.*?</font>", "", narrative, flags=re.DOTALL|re.IGNORECASE)
        narrative = re.sub(r"<[^>]+>", "", narrative)
        text_l = narrative.lower()
        # Extract first independent URL
        m = re.search(r"(?m)^(https?://\S+)$", block)
        if m:
            url = m.group(1)
        else:
            # Fallback: extract first href URL inside HTML
            m2 = re.search(r"href=\"(https?://[^\"\s]+)\"", block)
            url = m2.group(1) if m2 else ''
        host = urlparse(url).netloc.lower() if url else ''
        path = urlparse(url).path.lower() if url else ''

        # Prefer title-based HK detection to avoid false positives from link lists
        has_hk = any(k in title_l for k in hk_markers) or any(k in title_l for k in gba_markers)
        has_hk_path = any(seg in path for seg in ['/hong-kong', '/hongkong', '/greater-bay-area', '/gba/'])

        # SCMP must have explicit hong-kong path
        if 'scmp' in host and not has_hk_path:
            continue

        # Drop Google News relay unless content has HK markers
        if 'news.google.' in host and not (has_hk or has_hk_path):
            continue

        # Default rule: keep only if we can confirm HK/GBA markers in title or path indicates HK
        if not (has_hk or has_hk_path):
            continue

        kept.append(block.strip())

    return preface.rstrip() + ("\n\n" if preface and kept else "") + "\n\n".join(kept) + "\n"


def normalize_weather_heading(markdown: str) -> str:
    """Flatten weather heading so it appears in ToC as top-level like other news.

    Convert:
      ## 本日の香港の天気\n\n### 天気予報\n...
    to:
      ### 天気予報（香港）\n...
    """
    pattern = r"## 本日の香港の天気\s*\n\s*### 天気予報"
    return re.sub(pattern, "### 天気予報（香港）", markdown)


def main():
    if len(sys.argv) < 2:
        print("Usage: sanitize_article.py <article.md>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    content = path.read_text(encoding='utf-8')
    original = content

    # 1) Remove invalid weather block
    content = remove_invalid_weather_section(content)

    # 1b) Normalize weather heading so it's a top-level section (###)
    content = normalize_weather_heading(content)

    # 2) Deduplicate sections
    content = dedup_sections(content)

    # 3) Remove non-HK sections
    content = filter_non_hk_sections(content)

    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"🧹 Sanitized: {path}")
    else:
        print(f"✅ No sanitation needed: {path}")


if __name__ == "__main__":
    main()


