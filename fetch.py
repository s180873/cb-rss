import re, html, email.utils
import requests
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

FEEDS = {
    "rba.xml": ("https://www.rba.gov.au/rss/rss-cb-media-releases.xml",
                ("cash rate", "monetary policy", "statement by philip lowe", "governor", "interest rate")),
    "rbnz.xml": ("https://www.rbnz.govt.nz/rss/press-releases",
                 ("official cash rate", "monetary policy statement", "ocr")),
    "cad.xml": ("https://www.bankofcanada.ca/content_type/press-releases/feed/",
                ("policy rate", "monetary policy", "overnight rate", "bank rate", "interest rate")),
    # v-новое: пять недостающих зеркал
    "fed.xml": ("https://www.federalreserve.gov/feeds/press_monetary.xml",
                ("federal funds rate", "monetary policy", "fomc", "policy rate", "interest rate", "discount rate")),
    "ecb.xml": ("https://www.ecb.europa.eu/rss/press.xml",
                ("monetary policy", "interest rate", "governing council", "policy rate", "key interest")),
    "boe.xml": ("https://www.bankofengland.co.uk/rss/news",
                ("bank rate", "monetary policy", "mpc", "interest rate", "policy rate")),
    "boj.xml": ("https://www.boj.or.jp/en/rss/whatsnew.xml",
                ("monetary policy", "policy rate", "interest rate")),
    "snb.xml": ("https://news.google.com/rss/search?q=%22Swiss+National+Bank%22+policy+rate&hl=en-US&gl=US&ceid=US:en",
                ("policy rate", "monetary policy", "interest rate", "snb")),
}

MAX_ITEMS = 5
MAX_BODY = 3500

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text

def page_paragraphs(url):
    try:
        page = fetch(url)
    except Exception:
        return ""
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    parts = re.findall(r"<p[^>]*>(.*?)</p>", page, flags=re.S | re.I)
    out = []
    for p in parts:
        p = html.unescape(re.sub(r"<[^>]+>", " ", p))
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) > 80:
            out.append(p)
    return "\n\n".join(out)[:MAX_BODY]

def tag_local(el):
    return el.tag.rsplit("}", 1)[-1]

def parse_items(xml_text):
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return []
    items = []
    for el in root.iter():
        kind = tag_local(el)
        if kind not in ("item", "entry"):  # RSS и Atom
            continue
        d = {}
        for ch in el:
            k = tag_local(ch)
            if k == "link" and not (ch.text or "").strip():
                d["link"] = ch.get("href", "")  # Atom: <link href="..."/>
            else:
                d[k] = (ch.text or "").strip()
        if d.get("title") and d.get("link"):
            items.append(d)
    return items

def build_feed(name, url, keys, now):
    items = parse_items(fetch(url))
    if not items:
        print(name, "SKIP: upstream feed empty, mirror untouched")
        return
    hits = [it for it in items if any(k in it["title"].lower() for k in keys)]
    if not hits:
        print(name, "SKIP: no policy-related items, mirror untouched")
        return
    sel = hits[:MAX_ITEMS]
    lines = []
    for it in sel:
        body = page_paragraphs(it["link"])
        if len(body) < 200:
            body = html.unescape(it.get("description", ""))
        if not body:
            continue
        print(name, "->", it["title"][:60], "| body chars:", len(body))
        lines.append(
            "    <item>\n"
            "      <title>" + escape(it["title"]) + "</title>\n"
            "      <link>" + escape(it["link"]) + "</link>\n"
            "      <description>" + escape(body) + "</description>\n"
            "      <pubDate>" + escape(it.get("pubDate", now)) + "</pubDate>\n"
            "    </item>"
        )
    if not lines:
        print(name, "SKIP: no items with text, mirror untouched")
        return
    Path(name).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        "    <title>" + escape(name + " mirror") + "</title>\n"
        "    <link>" + escape(url) + "</link>\n"
        "    <description>mirror with full texts</description>\n"
        + "\n".join(lines) + "\n"
        "  </channel>\n"
        "</rss>\n",
        encoding="utf-8",
    )
    print(name, "OK: items:", len(lines))

now = email.utils.format_datetime(email.utils.localtime())
for name, (url, keys) in FEEDS.items():
    try:
        build_feed(name, url, keys, now)
    except Exception as e:
        print(name, "FAIL", e)
