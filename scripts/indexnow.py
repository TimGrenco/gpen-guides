#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver) that the site's pages changed.

Run after a deploy has gone live:   python3 scripts/indexnow.py
Submits every URL in sitemap.xml. Harmless to repeat; engines decide when to re-crawl.
"""
import json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import BASE_URL, INDEXNOW_KEY  # noqa: E402

urls = re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text())
host = re.sub(r"^https?://|/$", "", BASE_URL)
body = json.dumps({"host": host, "key": INDEXNOW_KEY, "keyLocation": f"{BASE_URL}{INDEXNOW_KEY}.txt",
                   "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                             headers={"Content-Type": "application/json; charset=utf-8"})
with urllib.request.urlopen(req, timeout=30) as r:
    print(r.status, f"submitted {len(urls)} URLs for {host}")
