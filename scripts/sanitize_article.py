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

    # 2) Deduplicate sections
    content = dedup_sections(content)

    # 3) Collapse excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)

    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"🧹 Sanitized: {path}")
    else:
        print(f"✅ No sanitation needed: {path}")


if __name__ == "__main__":
    main()


