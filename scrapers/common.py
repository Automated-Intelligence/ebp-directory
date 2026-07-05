"""Shared helpers for EBP Directory scrapers. Stdlib only — no pip dependencies."""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_CACHE = os.path.join(ROOT, "scrapers", "cache", "pages")
SOURCES_DIR = os.path.join(ROOT, "data", "sources")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 EBPDirectory/1.0"
)


def fetch(url, use_cache=True, delay=0.4, retries=3):
    """Fetch a URL with an on-disk cache, polite delay, and retries."""
    os.makedirs(PAGE_CACHE, exist_ok=True)
    key = hashlib.md5(url.encode()).hexdigest()
    path = os.path.join(PAGE_CACHE, key + ".html")
    if use_cache and os.path.exists(path):
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                html = r.read().decode("utf-8", errors="ignore")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            time.sleep(delay)
            return html
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                print(f"FAIL {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))
    return None


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url}: {e}", file=sys.stderr)
        return None


ENTITIES = {
    "&ndash;": "–", "&mdash;": "—", "&amp;": "&", "&#038;": "&",
    "&nbsp;": " ", "&#8217;": "'", "&#8216;": "'", "&#8220;": '"',
    "&#8221;": '"', "&#8211;": "–", "&#8212;": "—", "&quot;": '"',
    "&#039;": "'", "&rsquo;": "'", "&lsquo;": "'", "&hellip;": "...",
}


def clean(s):
    """Decode common HTML entities and collapse whitespace."""
    for k, v in ENTITIES.items():
        s = s.replace(k, v)
    s = re.sub(r"&#\d+;", "", s)
    s = s.replace("�", "–")  # replacement char: nearly always a mangled dash
    return re.sub(r"\s+", " ", s).strip()


def strip_tags(s):
    return clean(re.sub(r"<[^>]+>", " ", s))


def save_source(name, source_name, base_url, records, notes="", rating_scale=None):
    os.makedirs(SOURCES_DIR, exist_ok=True)
    out = {
        "source": name,
        "sourceName": source_name,
        "baseUrl": base_url,
        "scrapedAt": time.strftime("%Y-%m-%d"),
        "notes": notes,
        "ratingScale": rating_scale or {},
        "recordCount": len(records),
        "records": records,
    }
    path = os.path.join(SOURCES_DIR, name + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"{name}: {len(records)} records -> {path}")
    return path
