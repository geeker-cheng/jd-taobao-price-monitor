import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote

import requests

API_KEY = os.environ.get("HAODANKU_API_KEY", "").strip()
DOCS_ZIP_URL = "https://file.bc.haodanku.com/file/haodanku-openapi-docs.zip"
TIMEOUT = (6, 15)
TARGET_KEYWORDS = ["酷态科 AD653C", "酷态科 65W 2C1A"]
EXCLUDED = ("mini", "ultra", "屏显", "卡片", "90w", "100w", "套装", "套餐", "数据线", "充电线")


def redact(text):
    value = str(text)
    if API_KEY:
        value = value.replace(API_KEY, "***")
    return value


def compact(text):
    return str(text or "").lower().replace(" ", "").replace("-", "")


def looks_like_target(title):
    value = compact(title)
    brand = "酷态科" in value or "cuktech" in value
    model = "ad653c" in value or ("65w" in value and ("2c1a" in value or "三口" in value or "多口" in value))
    return brand and model and not any(compact(term) in value for term in EXCLUDED)


def find_goods(obj):
    found = []
    if isinstance(obj, dict):
        keys = set(obj)
        if keys & {"itemid", "item_id", "goods_id", "goodsId"} and keys & {"itemtitle", "title", "goods_name", "goodsName"}:
            found.append(obj)
        for value in obj.values():
            found.extend(find_goods(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(find_goods(value))
    return found


def pick(item, *keys):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def normalized_item(item):
    return {
        "id": pick(item, "itemid", "item_id", "goods_id", "goodsId"),
        "title": pick(item, "itemtitle", "title", "goods_name", "goodsName"),
        "shop": pick(item, "shopname", "shop_name", "shopName", "seller_name"),
        "price": pick(item, "itemprice", "price", "actual_price", "actualPrice"),
        "coupon_price": pick(item, "couponmoney", "coupon_price", "couponPrice"),
        "final_price": pick(item, "itemendprice", "end_price", "final_price"),
        "is_tmall": pick(item, "shoptype", "is_tmall", "istmall"),
    }


def double_encode(value):
    return quote(quote(value, safe=""), safe="")


def call_taobao_supersearch(keyword):
    encoded = double_encode(keyword)
    # Exact parameter pattern follows Haodanku's official Super Search example.
    url = (
        "http://v2.api.haodanku.com/supersearch/"
        f"apikey/{API_KEY}/keyword/{encoded}/back/20/min_id/1/"
        "tb_p/1/sort/0/is_tmall/1/is_coupon/0/limitrate/0"
    )
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        try:
            body = response.json()
        except Exception:
            body = None
        goods = [normalized_item(x) for x in find_goods(body)]
        candidates = [x for x in goods if looks_like_target(x.get("title"))]
        return {
            "keyword": keyword,
            "http": response.status_code,
            "api_code": body.get("code") if isinstance(body, dict) else None,
            "api_msg": body.get("msg") if isinstance(body, dict) else None,
            "result_count": len(goods),
            "candidates": candidates[:8],
            "ok": response.ok and isinstance(body, dict),
        }
    except Exception as exc:
        return {
            "keyword": keyword,
            "http": None,
            "api_code": None,
            "api_msg": None,
            "result_count": 0,
            "candidates": [],
            "ok": False,
            "error": redact(f"{type(exc).__name__}: {exc}"),
        }


def extract_official_docs():
    result = {
        "download_ok": False,
        "http": None,
        "files": [],
        "relevant_excerpts": [],
    }
    try:
        response = requests.get(DOCS_ZIP_URL, timeout=TIMEOUT)
        result["http"] = response.status_code
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            md_names = [name for name in archive.namelist() if name.lower().endswith(".md")]
            result["files"] = md_names
            excerpts = []
            for name in md_names:
                try:
                    text = archive.read(name).decode("utf-8", errors="replace")
                except Exception:
                    continue
                lines = text.splitlines()
                for i, line in enumerate(lines):
                    hit_platform = "京东" in line or "拼多多" in line
                    hit_intent = "搜索" in line or "详情" in line or "商品" in line
                    if not (hit_platform and hit_intent):
                        continue
                    start = max(0, i - 3)
                    end = min(len(lines), i + 12)
                    snippet = "\n".join(lines[start:end]).strip()
                    # Never let an unexpectedly echoed secret enter artifacts/logs.
                    snippet = redact(snippet)
                    excerpts.append({"file": name, "excerpt": snippet[:1800]})
                    if len(excerpts) >= 12:
                        break
                if len(excerpts) >= 12:
                    break
            result["relevant_excerpts"] = excerpts
            result["download_ok"] = True
    except Exception as exc:
        result["error"] = redact(f"{type(exc).__name__}: {exc}")
    return result


def main():
    if not API_KEY:
        print("ERROR: HAODANKU_API_KEY is not available to this workflow.")
        return 2

    search_results = [call_taobao_supersearch(keyword) for keyword in TARGET_KEYWORDS]
    docs = extract_official_docs()

    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "stage": "haodanku-first-probe",
        "target": "CUKTECH/酷态科 AD653C 65W 2C1A 老款方形充电器，灰色单体版",
        "secret_present": True,
        "secret_value_logged": False,
        "taobao_supersearch": search_results,
        "official_docs": docs,
        "notes": [
            "No affiliate conversion, purchase-link, order, or promotion-link endpoint is called.",
            "The API key is read only from HAODANKU_API_KEY and is never intentionally written to output.",
            "JD/PDD endpoint discovery is restricted to Haodanku's own official documentation package; no guessed paths are called.",
        ],
    }

    with open("haodanku-probe-result.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
