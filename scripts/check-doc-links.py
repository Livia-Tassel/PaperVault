"""Check local Markdown paths and heading anchors using only the standard library.

Third-party license documents are upstream snapshots and are excluded. External
URLs are not fetched. Code blocks and inline code are not treated as links.
"""
from __future__ import annotations

from collections import Counter
import html
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r'\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+(?:"[^"]*"|\'[^\']*\'))?\s*\)')
REFERENCE = re.compile(r'^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)', re.MULTILINE)
HTML_LINK = re.compile(r'\b(?:href|src)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def without_fences(markdown: str) -> str:
    """Mask fenced code while preserving line numbers for diagnostics."""
    fence: str | None = None
    output: list[str] = []
    for line in markdown.splitlines(keepends=True):
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        masked = fence is not None
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
                masked = True
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
        output.append(re.sub(r'[^\n]', ' ', line) if masked else line)
    return ''.join(output)


def heading_anchors(markdown: str) -> set[str]:
    content = without_fences(markdown)
    anchors = set(re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', content))
    counts: Counter[str] = Counter()
    for match in re.finditer(r'^\s{0,3}#{1,6}\s+(.+)$', content, re.MULTILINE):
        title = re.sub(r'\s+#+\s*$', '', match.group(1).strip())
        title = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', title)
        title = html.unescape(re.sub(r'<[^>]*>', '', title)).lower()
        slug = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        count = counts[slug]
        counts[slug] += 1
        anchors.add(slug if count == 0 else f'{slug}-{count}')
    return anchors


def main() -> int:
    tracked = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT,
    ).decode('utf-8').split('\0')
    documents = sorted({
        ROOT / name for name in tracked
        if name.endswith('.md') and (ROOT / name).is_file()
        and not name.startswith(('docs/third-party-licenses/', 'docs/third-party-sources/'))
    })
    anchor_cache: dict[Path, set[str]] = {}
    errors: list[str] = []
    checked = 0
    for document in documents:
        content = without_fences(document.read_text(encoding='utf-8'))
        content = re.sub(r'`+[^`\n]*`+', lambda match: ' ' * len(match.group()), content)
        for pattern in (LINK, REFERENCE, HTML_LINK):
            for match in pattern.finditer(content):
                target = html.unescape(match.group(1).strip('<>'))
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                checked += 1
                path = unquote(url.path)
                destination = (
                    ROOT / path.lstrip('/') if path.startswith('/')
                    else document.parent / path if path else document
                ).resolve()
                line = content.count('\n', 0, match.start()) + 1
                label = f'{document.relative_to(ROOT)}:{line}: {target}'
                if not destination.is_relative_to(ROOT) or not destination.exists():
                    errors.append(f'{label} (missing local path)')
                elif url.fragment and destination.suffix == '.md':
                    if destination not in anchor_cache:
                        anchor_cache[destination] = heading_anchors(destination.read_text(encoding='utf-8'))
                    if unquote(url.fragment) not in anchor_cache[destination]:
                        errors.append(f'{label} (missing heading anchor)')
    if errors:
        print('\n'.join(errors))
        print(f'FAIL: {len(errors)} broken local links across {len(documents)} Markdown files.')
        return 1
    print(f'PASS: {checked} local links across {len(documents)} Markdown files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
