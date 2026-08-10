import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("HAODANKU_API_KEY", "").strip()
DOCS_ZIP_URL = "https://file.bc.haodanku.com/file/haodanku-openapi-docs.zip"
TIMEOUT = (6, 15)
KEYWORDS = ["酷态科 AD653C", "酷态科 65W 氮化镓", "CUKTECH 65W 氮化镓"]
EXCLUDED = ("mini", "ultra", "屏显", "卡片", "90w", "100w", "套装", "套餐", "数据线", "充电线", "充电宝")


def redact(text):
    value = str(text)
    return value.replace(API_KEY, "***") if API_KEY else value


def compact(text):
    return str(text or "").lower().replace(" ", "").replace("-", "")


def pick(item, *keys):
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def find_goods(obj):
    found = []
    if isinstance(obj, dict):
        keys = set(obj)
        if keys & {"itemid", "item_id", "goods_id", "goodsId"} and keys & {"itemtitle", "title", "goodsname", "goodsName"}:
            found.append(obj)
        for value in obj.values():
            found.extend(find_goods(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(find_goods(value))
    return found


def normalize(item):
    return {
        "id": pick(item, "itemid", "item_id", "goods_id", "goodsId"),
        "title": pick(item, "itemtitle", "title", "goodsname", "goodsName"),
        "short_title": pick(item, "itemshorttitle", "short_title"),
        "shop": pick(item, "shopname", "shop_name", "shopName"),
        "price": pick(item, "itemprice", "price"),
        "final_price": pick(item, "itemendprice", "end_price", "final_price"),
        "coupon": pick(item, "couponmoney", "coupon_price", "couponPrice"),
    }


def target_candidate(item):
    title = compact(item.get("title"))
    shop = compact(item.get("shop"))
    brand_ok = "酷态科" in title or "cuktech" in title
    power_ok = "65w" in title
    multiport_ok = "多口" in title or "2c1a" in title or "双typec" in title or "三口" in title
    excluded = any(compact(term) in title for term in EXCLUDED)
    flagship = ("酷态科" in shop or "cuktech" in shop) and "旗舰店" in shop
    return brand_ok and power_ok and multiport_ok and not excluded and flagship


def markdown_section(text, heading):
    match = re.search(rf"^###\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return None
    tail = text[match.end():]
    next_match = re.search(r"^###\s+", tail, re.MULTILINE)
    end = match.end() + (next_match.start() if next_match else len(tail))
    return text[match.start():end].strip()


def parse_section(section):
    if not section:
        return None

    def field(label):
        m = re.search(rf"^-\s*{re.escape(label)}：\s*(.+)$", section, re.MULTILINE)
        return m.group(1).strip() if m else None

    return {
        "method": field("请求方式"),
        "path": field("接口路径"),
        "required": field("必填参数"),
        "optional": field("可选参数"),
        "return_fields": field("返回核心字段"),
        "permission": field("权限要求"),
    }


def load_taobao_docs():
    response = requests.get(DOCS_ZIP_URL, timeout=TIMEOUT)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        name = next(n for n in archive.namelist() if n.replace("\\", "/").endswith("interfaces/商品接口.md"))
        text = archive.read(name).decode("utf-8", errors="replace")
    return {
        "search": parse_section(markdown_section(text, "淘宝商品搜索")),
        "detail": parse_section(markdown_section(text, "淘宝单品详情")),
    }


def endpoint_url(path):
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return "https://" + path.lstrip("/")


def search(keyword, spec):
    params = {"apikey": API_KEY, "keyword": keyword}
    optional = spec.get("optional") or ""
    if "min_id" in optional:
        params["min_id"] = 1
    if "back" in optional:
        params["back"] = 50
    try:
        response = requests.get(endpoint_url(spec["path"]), params=params, timeout=TIMEOUT)
        body = response.json()
        goods = [normalize(x) for x in find_goods(body)]
        return {
            "keyword": keyword,
            "http": response.status_code,
            "code": pick(body, "code", "status"),
            "msg": pick(body, "msg", "message"),
            "count": len(goods),
            "official_store_results": [x for x in goods if ("酷态科" in compact(x.get("shop")) or "cuktech" in compact(x.get("shop"))) and "旗舰店" in compact(x.get("shop"))][:15],
            "candidates": [x for x in goods if target_candidate(x)][:10],
        }
    except Exception as exc:
        return {"keyword": keyword, "error": redact(f"{type(exc).__name__}: {exc}"), "candidates": []}


def detail(item, spec):
    required = (spec.get("required") or "").lower()
    params = {"apikey": API_KEY}
    if "itemid" in required:
        params["itemid"] = item["id"]
    elif "item_id" in required:
        params["item_id"] = item["id"]
    else:
        return {"search_item": item, "called": False, "reason": f"unrecognized documented required params: {spec.get('required')}"}

    try:
        response = requests.get(endpoint_url(spec["path"]), params=params, timeout=TIMEOUT)
        body = response.json()
        goods = [normalize(x) for x in find_goods(body)]
        text = json.dumps(body, ensure_ascii=False)
        terms = ["AD653C", "2C1A", "65W", "灰色", "单体", "三口", "多口"]
        return {
            "search_item": item,
            "called": True,
            "http": response.status_code,
            "code": pick(body, "code", "status"),
            "msg": pick(body, "msg", "message"),
            "normalized_goods": goods[:5],
            "term_hits": {term: term.lower() in text.lower() for term in terms},
            "response_preview": redact(text)[:3500],
        }
    except Exception as exc:
        return {"search_item": item, "called": True, "error": redact(f"{type(exc).__name__}: {exc}")}


def main():
    if not API_KEY:
        print("ERROR: HAODANKU_API_KEY is not available to this workflow.")
        return 2

    docs = load_taobao_docs()
    searches = [search(keyword, docs["search"]) for keyword in KEYWORDS]

    seen = set()
    candidates = []
    for result in searches:
        for item in result.get("candidates", []):
            if item.get("id") and item["id"] not in seen:
                seen.add(item["id"])
                candidates.append(item)

    details = [detail(item, docs["detail"]) for item in candidates[:5]]

    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "stage": "haodanku-taobao-exact-product-detail",
        "target": "CUKTECH/酷态科 AD653C 65W 2C1A 老款方形充电器，灰色单体版",
        "secret_present": True,
        "secret_value_logged": False,
        "official_docs": docs,
        "searches": searches,
        "candidate_count": len(candidates),
        "details": details,
        "notes": [
            "Only Haodanku ordinary Taobao search/detail endpoints are called.",
            "No conversion, promotion-link, order, or purchase-link endpoint is called.",
            "Only brand flagship-store results are eligible for detail verification.",
        ],
    }

    with open("haodanku-probe-result.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
