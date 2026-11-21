import requests, pathlib

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

FEEDS = {
    "rba.xml":  "https://www.rba.gov.au/rss/rss-cb-media-releases.xml",
    "rbnz.xml": "https://www.rbnz.govt.nz/rss/press-releases",
}

for name, url in FEEDS.items():
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        print(name, r.status_code, len(r.content))
        if r.status_code == 200 and len(r.content) > 200:
            pathlib.Path(name).write_bytes(r.content)
        else:
            print(name, "SKIP: not usable")
    except Exception as e:
        print(name, "FAIL", e)
