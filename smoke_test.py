import html
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import unquote

import requests

CONNECT_TIMEOUT = 6
READ_TIMEOUT = 12
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    "User-Agent": UA,
}

TARGET = {
    "model": "AD653C",
    "name": "CUKTECH/酷态科 65W 2C1A 氮化镓充电器 AD653C 灰色单体版",
    "jd_sku": "100068768088",
}

# These pages were found from public search results and explicitly identify the
# same AD653C product on the corresponding platform. They are used only as
# free auxiliary discovery/verification sources, not as purchase links.
AUX_PAGES = [
    {
        "platform": "tmall",
        "url": "https://www.smzdm.com/p/178967194/",
        "expected_terms": ["AD653C", "天猫", "灰色单体版", "2C1A"],
    },
    {
        "platform": "pdd",
        "url": "https://www.smzdm.com/p/177755710/",
        "expected_terms": ["AD653C", "拼多多", "2C1A"],
    },
]


def safe_get(url, *, params=None):
    try:
        r = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True,
        )
        return r, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def compact_text(raw):
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def find_external_links(raw):
    links = []
    patterns = [
        r'https?://[^"\'<>\s]+',
        r'//[^"\'<>\s]+',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, raw, flags=re.I):
            candidate = html.unescape(unquote(match)).rstrip("\\")
            lower = candidate.lower()
            if any(domain in lower for domain in [
                "jd.com", "tmall.com", "taobao.com", "yangkeduo.com", "pinduoduo.com"
            ]):
                if candidate.startswith("//"):
                    candidate = "https:" + candidate
                if candidate not in links:
                    links.append(candidate)
    return links[:20]


def price_snippets(text):
    snippets = []
    patterns = [
        r"(?:¥|￥)\s*\d+(?:\.\d+)?",
        r"\d+(?:\.\d+)?\s*元",
        r"(?:到手价|实付|售价|价格)[^。；,，]{0,30}\d+(?:\.\d+)?",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.I):
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 80)
            snippet = text[start:end]
            if "AD653C" in snippet.upper() or "酷态科" in snippet or "CUKTECH" in snippet.upper():
                if snippet not in snippets:
                    snippets.append(snippet)
            if len(snippets) >= 12:
                return snippets
    return snippets


def probe_jd_public_price():
    url = "https://p.3.cn/prices/mgets"
    params = {"skuIds": f"J_{TARGET['jd_sku']}"}
    r, error = safe_get(url, params=params)
    result = {
        "source": "jd_public_price_endpoint",
        "url": r.url if r is not None else url,
        "http": r.status_code if r is not None else None,
        "error": error,
        "json": None,
        "price": None,
        "market_price": None,
        "ok": False,
    }
    if r is None:
        return result
    try:
        body = r.json()
        result["json"] = body
        row = body[0] if isinstance(body, list) and body else {}
        result["price"] = row.get("p")
        result["market_price"] = row.get("m")
        result["ok"] = r.status_code == 200 and row.get("id") == f"J_{TARGET['jd_sku']}" and row.get("p") not in (None, "", "-1")
    except Exception as exc:
        result["error"] = f"json parse: {type(exc).__name__}: {exc}"
        result["body_preview"] = r.text[:1000]
    return result


def probe_jd_item_page():
    url = f"https://item.jd.com/{TARGET['jd_sku']}.html"
    r, error = safe_get(url)
    result = {
        "source": "jd_item_page",
        "url": r.url if r is not None else url,
        "http": r.status_code if r is not None else None,
        "error": error,
        "contains_ad653c": False,
        "contains_65w": False,
        "contains_2c1a": False,
        "title": None,
        "body_preview": None,
        "ok": False,
    }
    if r is None:
        return result
    raw = r.text
    text = compact_text(raw)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    if title_match:
        result["title"] = compact_text(title_match.group(1))[:300]
    result["contains_ad653c"] = "AD653C" in text.upper()
    result["contains_65w"] = "65W" in text.upper()
    result["contains_2c1a"] = "2C1A" in text.upper()
    pos = text.upper().find("AD653C")
    if pos >= 0:
        result["body_preview"] = text[max(0, pos - 250):pos + 500]
    else:
        result["body_preview"] = text[:800]
    result["ok"] = r.status_code == 200 and result["contains_ad653c"]
    return result


def probe_aux_page(case):
    r, error = safe_get(case["url"])
    result = {
        "platform": case["platform"],
        "source": "smzdm_public_page",
        "url": r.url if r is not None else case["url"],
        "http": r.status_code if r is not None else None,
        "error": error,
        "expected_terms": case["expected_terms"],
        "term_hits": {},
        "external_links": [],
        "price_snippets": [],
        "text_preview": None,
        "ok": False,
    }
    if r is None:
        return result
    raw = r.text
    text = compact_text(raw)
    result["term_hits"] = {term: (term.lower() in text.lower()) for term in case["expected_terms"]}
    result["external_links"] = find_external_links(raw)
    result["price_snippets"] = price_snippets(text)
    pos = text.upper().find("AD653C")
    result["text_preview"] = text[max(0, pos - 300):pos + 900] if pos >= 0 else text[:1200]
    result["ok"] = r.status_code == 200 and result["term_hits"].get("AD653C", False)
    return result


def main():
    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "stage": "exact-product-source-probe",
        "target": TARGET,
        "jd": {
            "public_price": probe_jd_public_price(),
            "item_page": probe_jd_item_page(),
        },
        "auxiliary_sources": [probe_aux_page(case) for case in AUX_PAGES],
        "notes": [
            "No account login, cookies, affiliate conversion or purchase-link API is used.",
            "The JD public endpoint is probed only for the exact known SKU 100068768088.",
            "SMZDM pages are treated as auxiliary discovery/verification sources, not authoritative checkout prices.",
        ],
    }

    with open("smoke-result.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
