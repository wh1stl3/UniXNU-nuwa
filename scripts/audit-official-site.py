"""Read-only site walk: Chinese HTML pages, anchors, links and source hashes.

Raw HTML and readable main content go to ignored out/. Evidence contains only
structure/metadata, not a mirror of upstream code. No device or image access.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit, urldefrag, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://unixnu.com'
OUT = ROOT / 'out/official-site-audit'
EVIDENCE = ROOT / 'reports/official-site-audit'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.headings, self.text = [], [], [], []
        self.in_main = False
        self.heading = None
        self.title = ''
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'main':
            self.in_main = True
        if tag == 'title':
            self.in_title = True
        if self.in_main and tag in ('h1', 'h2', 'h3', 'h4'):
            self.heading = [tag, attrs.get('id'), '']
        if self.in_main and tag in ('p', 'tr', 'li', 'pre', 'h1', 'h2', 'h3', 'h4'):
            self.text.append('\n')
        if self.in_main and tag in ('td', 'th'):
            self.text.append(' | ')

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False
        if tag == 'title':
            self.in_title = False
        if self.heading and tag == self.heading[0]:
            self.headings.append(dict(level=int(tag[1]), id=self.heading[1], text=self.heading[2].strip()))
            self.heading = None
        if self.in_main and tag in ('p', 'tr', 'li', 'pre', 'h1', 'h2', 'h3', 'h4'):
            self.text.append('\n')

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.heading:
            self.heading[2] += data
        if self.in_main:
            self.text.append(data)


def page_url(link, base):
    url = urldefrag(urljoin(base, link))[0]
    parsed = urlsplit(url)
    if parsed.netloc != 'unixnu.com' or not parsed.path.startswith('/zh/') or parsed.query:
        return None
    if '.' in parsed.path.rsplit('/', 1)[-1]:
        return None
    return url


def fetch(url):
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as response:
            raw, final = response.read(), response.url
            parser = Page()
            parser.feed(raw.decode('utf-8'))
            stem = urlsplit(url).path.strip('/').replace('/', '__') or 'index'
            (OUT / (stem + '.html')).write_bytes(raw)
            lines = [line.strip() for line in ''.join(parser.text).splitlines() if line.strip()]
            (OUT / (stem + '.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return dict(url=url, final_url=final, status=response.status, bytes=len(raw),
                        sha256=sha256(raw).hexdigest(), title=parser.title,
                        headings=parser.headings, ids=parser.ids, links=sorted(set(parser.links)),
                        readable_path=(OUT / (stem + '.txt')).relative_to(ROOT).as_posix())
    except Exception as error:
        return dict(url=url, error=f'{type(error).__name__}: {error}')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    cached = '--cached' in sys.argv
    prior = json.loads((EVIDENCE / 'structure.json').read_text(encoding='utf-8')) if cached else None
    pending = set() if cached else {ORIGIN + '/zh/porting/', ORIGIN + '/zh/devices/'}
    records = {r['url']: r for r in prior['pages']} if cached else {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        while pending:
            batch = sorted(pending - records.keys())
            if not batch:
                break
            if len(records) + len(batch) > 300:
                raise RuntimeError('Unexpected site size; inspect boundary before continuing')
            pending = set()
            for record in pool.map(fetch, batch):
                records[record['url']] = record
                print(record['url'], record.get('status', record.get('error')), flush=True)
                for link in record.get('links', []):
                    target = page_url(link, record['url'])
                    if target and target not in records:
                        pending.add(target)
    anchors = []
    external = set()
    for source, record in records.items():
        # Public group invitation URLs carry query tokens; they add nothing to
        # the structure audit and should not be republished in Git evidence.
        record['links'] = sorted(set(urlsplit(link)._replace(query='').geturl()
            if urlsplit(link).netloc not in ('', 'unixnu.com') else link
            for link in record.get('links', [])))
        for link in record.get('links', []):
            absolute = urljoin(source, link)
            target, fragment = urldefrag(absolute)
            if fragment and target in records and 'error' not in records[target]:
                if unquote(fragment) not in records[target]['ids']:
                    anchors.append(dict(source=source, target=absolute))
            if urlsplit(absolute).netloc not in ('', 'unixnu.com'):
                external.add(absolute)
    # VitePress embeds every published Markdown route in its build hash map.
    # Compare it with the hyperlink walk to detect pages absent from navigation.
    html = (OUT / 'zh__porting.html').read_text(encoding='utf-8')
    match = re.search(r'window\.__VP_HASH_MAP__=JSON\.parse\(("(?:\\.|[^"\\])*")\)', html)
    if not match:
        raise RuntimeError('Published route manifest missing; cannot claim complete route coverage')
    manifest = json.loads(json.loads(match.group(1)))
    chinese = sorted(key for key in manifest if key.startswith('zh_'))
    sources = set()
    for record in records.values():
        for link in record.get('links', []):
            prefix = 'https://github.com/UniXNU/UniXNU/edit/main/docs/'
            if link.startswith(prefix):
                sources.add(link[len(prefix):].replace('/', '_'))
    # The home page has no edit link; its route was fetched directly.
    if ORIGIN + '/zh/' in records:
        sources.add('zh_index.md')
    unvisited = sorted(set(chinese) - sources)
    evidence = dict(captured_at=prior['captured_at'] if cached else datetime.now(timezone.utc).isoformat(),
                    scope='All Chinese HTML pages reachable from the two user URLs, including site navigation; assets and English duplicates excluded',
                    external_url_queries='Omitted from committed link metadata',
                    pages=sorted(records.values(), key=lambda item: item['url']),
                    failed_pages=[r for r in records.values() if 'error' in r],
                    missing_anchor_targets=anchors, external_links=sorted(external),
                    published_route_manifest=dict(all_language_route_count=len(manifest),
                        all_routes=sorted(manifest),
                        chinese_route_count=len(chinese), chinese_routes=chinese,
                        chinese_routes_missing_from_walk=unvisited))
    (EVIDENCE / 'structure.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Summary:', len(records), 'pages;', len(evidence['failed_pages']), 'failures;', len(anchors),
          'missing anchors;', len(unvisited), 'published Chinese routes not visited')


if __name__ == '__main__':
    main()
