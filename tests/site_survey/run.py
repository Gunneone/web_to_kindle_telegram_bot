#!/usr/bin/env python3
"""
Site survey: run the real scrape -> EPUB pipeline against live article URLs and check the results.

This is a network tool, not a unit test. Usage:

    python tests/site_survey/run.py [urls.txt] [--out DIR] [--workers N]

For every URL it records extracted metadata, word counts versus a reference (JSON-LD articleBody or
the page's <article> paragraphs), image counts and formats inside the EPUB, image references that
don't resolve, and mojibake. Results go to DIR/results.jsonl and DIR/report.md.
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'src'))

from bs4 import BeautifulSoup  # noqa: E402
from PIL import Image  # noqa: E402

import epub_converter  # noqa: E402
from web_scraper import get_website_content  # noqa: E402
from web_scraper.http import fetch  # noqa: E402
from web_scraper.metadata import extract_metadata  # noqa: E402

MOJIBAKE = re.compile('â€|Ã[\u0080-¿]|Â |â\u0080')
_current = threading.local()
LOGS = defaultdict(list)


class Collector(logging.Handler):
    """Attach log records to the URL being processed by the current worker thread."""

    def emit(self, record):
        url = getattr(_current, 'url', None)
        if url:
            LOGS[url].append(f"{record.levelname}:{record.name}:{record.getMessage()[:200]}")


def reference_words(url: str) -> int:
    """Independent estimate of the article length to detect truncated extraction."""
    try:
        page = fetch(url)
    except Exception:
        return 0
    soup = BeautifulSoup(page.html, 'lxml')
    container = soup.find('article') or soup.find('main')
    paragraph_words = len(' '.join(p.get_text(' ') for p in container.find_all('p')).split()) if container else 0
    return max(paragraph_words, extract_metadata(page.html, page.final_url, soup=soup).body_words)


def image_format(data: bytes) -> str:
    if b'<svg' in data[:1024].lower():
        return 'svg'
    try:
        return Image.open(io.BytesIO(data)).format.lower()
    except Exception:
        return 'unknown'


def survey(url: str) -> dict:
    _current.url = url
    result = {'url': url}
    started = time.time()
    try:
        article = get_website_content(url)
        result.update(title=article.Title, author=article.Author, published=article.Published_At,
                      publication=article.Publication, language=article.Language, preview=article.Is_Preview)
        logs = ' '.join(LOGS[url])
        result['scraper'] = ('medium-rss' if 'Medium RSS' in logs else 'medium' if 'Medium Extractor' in logs
                             else 'substack' if 'Substack Extractor' in logs
                             else 'trafilatura' if 'Using trafilatura' in logs else 'readability')
        soup = BeautifulSoup(article.Content, 'lxml')
        text = soup.get_text(' ')
        result['words'] = len(text.split())
        result['images'] = len(soup.find_all('img'))
        result['mojibake'] = len(MOJIBAKE.findall(text))

        path = epub_converter.convert_to_epub(article)
        with zipfile.ZipFile(path) as epub_zip:
            names = epub_zip.namelist()
            xhtml = BeautifulSoup(epub_zip.read('EPUB/content.xhtml'), 'html.parser')
            sources = [img.get('src') for img in xhtml.find_all('img')]
            result['epub_images'] = len(sources)
            result['epub_unresolved'] = sum(1 for src in sources if f'EPUB/{src}' not in names)
            result['epub_duplicate_names'] = len(names) - len(set(names))
            formats = defaultdict(int)
            for name in names:
                if name.startswith('EPUB/Images/'):
                    formats[image_format(epub_zip.read(name))] += 1
            result['epub_formats'] = dict(formats)
        failed = re.search(r'Embedded (\d+) images, (\d+) image references failed', logs + ' '.join(LOGS[url]))
        result['images_failed'] = int(failed.group(2)) if failed else 0
        result['reference_words'] = reference_words(url)
        result['ok'] = True
    except Exception as e:
        result['ok'] = False
        result['error'] = f"{type(e).__name__}: {e}"
        result['traceback'] = traceback.format_exc()[-800:]
    result['seconds'] = round(time.time() - started, 1)
    result['warnings'] = [line for line in LOGS[url] if line.startswith(('WARNING', 'ERROR'))][:10]
    return result


def flags(r: dict) -> list[str]:
    if not r.get('ok'):
        return ['FAIL']
    found = []
    if r['reference_words'] > 200 and r['words'] < 0.7 * r['reference_words']:
        found.append('TRUNCATED?')
    if not r['author']:
        found.append('no-author')
    if not r['published']:
        found.append('no-date')
    if r['images_failed']:
        found.append(f"img-failed:{r['images_failed']}")
    if r['epub_unresolved'] or r['epub_duplicate_names']:
        found.append('EPUB-INVALID')
    if set(r['epub_formats']) - {'jpeg', 'png', 'gif', 'svg'}:
        found.append('UNSUPPORTED-IMG')
    if r['mojibake']:
        found.append('MOJIBAKE')
    if r['preview']:
        found.append('preview')
    return found


def write_report(results: list[dict], out_dir: str) -> str:
    lines = ['| URL | Scraper | Title | Author | Date | Lang | Words (ref) | Images | Time | Flags |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for r in results:
        short = re.sub(r'^https?://(www\.)?', '', r['url'])[:55]
        if r.get('ok'):
            lines.append(f"| {short} | {r['scraper']} | {(r['title'] or '')[:45]} | {(r['author'] or '')[:25]} | "
                         f"{r['published'] or ''} | {r['language'] or ''} | {r['words']} ({r['reference_words']}) | "
                         f"{r['epub_images']}/{r['images']} | {r['seconds']}s | {', '.join(flags(r))} |")
        else:
            lines.append(f"| {short} | | | | | | | | {r['seconds']}s | FAIL: {r['error'][:80]} |")
    ok = sum(1 for r in results if r.get('ok'))
    clean = sum(1 for r in results if r.get('ok') and not [f for f in flags(r) if f.isupper() or f == 'FAIL'])
    lines.append('')
    lines.append(f"{ok}/{len(results)} converted, {clean} without serious flags (uppercase flags are serious).")
    report = '\n'.join(lines)
    with open(os.path.join(out_dir, 'report.md'), 'w', encoding='utf-8') as f:
        f.write(report + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('urls', nargs='?', default=os.path.join(HERE, 'urls.txt'))
    parser.add_argument('--out', default=None, help='output directory (default: a new temp directory)')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()

    with open(args.urls, encoding='utf-8') as f:
        urls = [line.split('#')[0].strip() for line in f if line.strip() and not line.lstrip().startswith('#')]
    urls = [u for u in urls if u]
    out_dir = os.path.abspath(args.out or tempfile.mkdtemp(prefix='site-survey-'))
    os.makedirs(out_dir, exist_ok=True)
    os.chdir(out_dir)  # scrapers write ./output/html and ./output/epubs

    root = logging.getLogger()
    root.handlers = [Collector()]
    root.setLevel(logging.INFO)
    logging.getLogger('trafilatura').setLevel(logging.ERROR)

    print(f"Surveying {len(urls)} URLs, output in {out_dir}", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor, \
            open(os.path.join(out_dir, 'results.jsonl'), 'w', encoding='utf-8') as jsonl:
        for r in executor.map(survey, urls):
            results.append(r)
            jsonl.write(json.dumps(r) + '\n')
            print(f"{'OK  ' if r.get('ok') else 'FAIL'} {r['seconds']:>5}s {r['url'][:80]} {' '.join(flags(r))}",
                  flush=True)
    print()
    print(write_report(results, out_dir))


if __name__ == '__main__':
    main()
