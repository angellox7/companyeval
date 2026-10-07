"""Pull readable text from a deck or a public website."""

import json
import re
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

WEBSITE_LIMIT_BYTES = 1_000_000
WEBSITE_TIMEOUT_SECONDS = 15
MAX_COMPANY_PAGES = 4
MAX_JSON_SENTENCES = 40
DESCRIPTION_META = {"description", "og:description", "twitter:description"}
COMPANY_PAGE_WORDS = frozenset(
    {"about", "company", "product", "pricing", "customers", "team", "story"}
)
_BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "tr", "section"}


class ExtractError(Exception):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.descriptions = []
        self.script_bodies = []
        self.links = []
        self._skip = 0
        self._script_parts = None
        self._link_href = None
        self._link_parts = None

    def handle_starttag(self, tag, attrs):
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            if tag == "script":
                self._script_parts = []
            return
        if self._skip:
            return
        if tag == "meta":
            key = (attr.get("name") or attr.get("property") or "").lower()
            content = attr.get("content", "").strip()
            if key in DESCRIPTION_META and content:
                self.descriptions.append(content)
        if tag == "a":
            self._link_href = attr.get("href", "")
            self._link_parts = []
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self._script_parts is not None:
            body = "".join(self._script_parts).strip()
            if body[:1] in "{[":
                self.script_bodies.append(body)
            self._script_parts = None
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
            return
        if tag == "a" and self._link_parts is not None:
            href = self._link_href or ""
            text = "".join(self._link_parts)
            self._link_href = None
            self._link_parts = None
            if href:
                self.links.append((href, text))

    def handle_data(self, data):
        if self._script_parts is not None and self._skip:
            self._script_parts.append(data)
            return
        if self._skip:
            return
        self.parts.append(data)
        if self._link_parts is not None:
            self._link_parts.append(data)


def _collapse(value):
    return " ".join((value or "").split())


def _contains(haystack, needle):
    folded = " ".join((haystack or "").split()).casefold()
    return _collapse(needle).casefold() in folded


def _looks_like_sentence(value):
    text = _collapse(value)
    if len(text) < 40 or len(text.split(" ")) < 4:
        return False
    lowered = text.casefold()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return False
    return True


def _json_sentences(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    found = []

    def walk(node):
        if isinstance(node, str):
            sentence = _collapse(node)
            if _looks_like_sentence(sentence):
                found.append(sentence)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


def _parse_html(html):
    parser = _TextExtractor()
    parser.feed(html or "")
    parser.close()
    return parser


def _compose_text(parser):
    visible = "".join(parser.parts)
    visible = re.sub(r"[ \t]+\n", "\n", visible)
    visible = re.sub(r"\n{3,}", "\n\n", visible).strip()

    descriptions = []
    seen = set()
    for raw in parser.descriptions:
        sentence = _collapse(raw)
        key = sentence.casefold()
        if not sentence or key in seen or (visible and _contains(visible, sentence)):
            continue
        seen.add(key)
        descriptions.append(sentence)

    combined = "\n\n".join(part for part in (descriptions + ([visible] if visible else [])) if part)
    extra = []
    for raw in parser.script_bodies:
        for sentence in _json_sentences(raw):
            if _contains(combined, sentence) or any(_contains(item, sentence) for item in extra):
                continue
            extra.append(sentence)
            if len(extra) >= MAX_JSON_SENTENCES:
                break
        if len(extra) >= MAX_JSON_SENTENCES:
            break

    blocks = descriptions
    if visible:
        blocks.append(visible)
    if extra:
        blocks.append("\n".join(extra))
    return "\n\n".join(blocks).strip()


def html_to_text(html):
    return _compose_text(_parse_html(html))


def _tokens(value):
    return [token for token in re.split(r"[^a-z0-9]+", (value or "").lower()) if token]


def _is_company_link(path, anchor):
    tokens = _tokens(path) + _tokens(anchor)
    return any(token in COMPANY_PAGE_WORDS for token in tokens)


def _page_key(url):
    parsed = urlparse(url)
    return (
        parsed.scheme.lower(),
        (parsed.hostname or "").lower(),
        parsed.path or "/",
        parsed.query,
    )


def _download(url):
    request = Request(url, headers={"User-Agent": "Companyeval/1.0"})
    try:
        with urlopen(request, timeout=WEBSITE_TIMEOUT_SECONDS) as response:
            final_url = response.geturl() or url
            raw = response.read(WEBSITE_LIMIT_BYTES + 1)
            truncated = len(raw) > WEBSITE_LIMIT_BYTES
            raw = raw[:WEBSITE_LIMIT_BYTES]
            charset = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
    except HTTPError as exc:
        raise ExtractError(f"The website returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ExtractError("The website could not be reached.") from exc
    except TimeoutError as exc:
        raise ExtractError("The website took too long to respond.") from exc
    return html, truncated, final_url


def _company_page_urls(parser, page_url):
    host = (urlparse(page_url).hostname or "").lower()
    seen = {_page_key(page_url)}
    urls = []
    for href, anchor in parser.links:
        if len(urls) >= MAX_COMPANY_PAGES:
            break
        absolute = urljoin(page_url, href.strip())
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if (parsed.hostname or "").lower() != host:
            continue
        if not _is_company_link(parsed.path, anchor):
            continue
        key = _page_key(absolute)
        if key in seen:
            continue
        seen.add(key)
        urls.append(absolute)
    return urls


def extract_pdf(fileobj):
    from pypdf import PdfReader

    reader = PdfReader(fileobj)
    chunks = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        chunks.append(f"[Page {index}]\n{text.strip()}")
    return "\n\n".join(chunks).strip()


def pdf_has_text(body):
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[Page ") and stripped.endswith("]"):
            continue
        return True
    return False


def fetch_website(url):
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ExtractError("Website URLs use http or https.")

    html, truncated, final_url = _download(url)
    parser = _parse_html(html)
    text = _compose_text(parser)
    if not text:
        raise ExtractError("The website returned no readable text.")

    blocks = [f"{final_url}\n{text}"]
    host = (urlparse(final_url).hostname or "").lower()
    for extra_url in _company_page_urls(parser, final_url):
        try:
            extra_html, _extra_truncated, extra_final = _download(extra_url)
        except ExtractError:
            continue
        if (urlparse(extra_final).hostname or "").lower() != host:
            continue
        extra_text = html_to_text(extra_html)
        if not extra_text.strip():
            continue
        blocks.append(f"{extra_final}\n{extra_text}")
    return "\n\n".join(blocks), truncated
