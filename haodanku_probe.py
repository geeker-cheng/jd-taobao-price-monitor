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
        id_keys = {"itemid", "item_id", "goods_id", "goodsId"}
        title_keys = {"itemtitle", "title", "goodsname", "goodsName"}
        if keys & id_keys and keys & title_keys:
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


def split_h3_sections(text):
    matches = list(re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append({
            "heading": match.group(1).strip(),
            "text": text[match.start():end].strip(),
        })
    return sections


def parse_section(section):
    if not section:
        return None
    text = section["text"] if isinstance(section, dict) else str(section)

    def field(label):
        match = re.search(rf"^-\s*{re.escape(label)}：\s*(.+)$", text, re.MULTILINE)
        return match.group(1).strip() if match else None

    return {
        "heading": section.get("heading") if isinstance(section, dict) else None,
        "method": field("请求方式"),
        "path": field("接口路径"),
        "required": field("必填参数"),
        "optional": field("可选参数"),
        "return_fields": field("返回核心字段"),
        "permission": field("权限要求"),
        "section_preview": redact(text)[:2400],
    }


def choose_taobao_sections(sections):
    taobao = [section for section in sections if "淘宝" in section["heading"]]

    search_section = next(
        (section for section in taobao if "搜索" in section["heading"] and "转链" not in section["heading"]),
        None,
    )

    detail_candidates = []
    for section in taobao:
        heading = section["heading"]
        body = section["text"]
        if "接口路径" not in body:
            continue
        if any(term in heading for term in ("转链", "列表", "搜索", "订单", "活动")):
            continue
        detail_signal = "详情" in heading or "单品" in heading or "商品详情" in body or "单品详情" in body
        if detail_signal:
            detail_candidates.append(section)

    detail_section = detail_candidates[0] if detail_candidates else None
    return {
        "all_taobao_headings": [section["heading"] for section in taobao],
        "search": parse_section(search_section),
        "detail": parse_section(detail_section),
        "detail_candidate_headings": [section["heading"] for section in detail_candidates],
    }


def load_taobao_docs():
    result = {
        "download_ok": False,
        "http": None,
        "all_taobao_headings": [],
        "detail_candidate_headings": [],
        "search": None,
        "detail": None,
    }
    try:
        response = requests.get(DOCS_ZIP_URL, timeout=TIMEOUT)
        result["http"] = response.status_code
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            name = next(
                n for n in archive.namelist()
                if n.replace("\\", "/").endswith("interfaces/商品接口.md")
            )
            text = archive.read(name).decode("utf-8", errors="replace")
        result.update(choose_taobao_sections(split_h3_sections(text)))
        result["download_ok"] = True
    except Exception as exc:
        result["error"] = redact(f"{type(exc).__name__}: {exc}")
    return result


def endpoint_url(path):
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return "https://" + path.lstrip("/")


def search(keyword, spec):
    if not spec or not spec.get("path"):
        return {
            "keyword": keyword,
            "called": False,
            "reason": "official Taobao search interface was not discovered",
            "candidates": [],
        }

    params = {"apikey": API_KEY, "keyword": keyword}
    optional = spec.get("optional") or ""
    if "min_id" in optional:
        params["min_id"] = 1
    if "back" in optional:
        params["back"] = 50

    try:
        response = requests.get(endpoint_url(spec["path"]), params=params, timeout=TIMEOUT)
        try:
            body = response.json()
        except Exception:
            body = None
        goods = [normalize(x) for x in find_goods(body)]
        official_store = [
            x for x in goods
            if ("酷态科" in compact(x.get("shop")) or "cuktech" in compact(x.get("shop")))
            and "旗舰店" in compact(x.get("shop"))
        ]
        return {
            "keyword": keyword,
            "called": True,
            "http": response.status_code,
            "code": pick(body, "code", "status"),
            "msg": pick(body, "msg", "message"),
            "count": len(goods),
            "official_store_results": official_store[:20],
            "candidates": [x for x in goods if target_candidate(x)][:10],
        }
    except Exception as exc:
        return {
            "keyword": keyword,
            "called": True,
            "error": redact(f"{type(exc).__name__}: {exc}"),
            "candidates": [],
        }


def documented_id_parameter(required):
    required_lower = (required or "").lower()
    for name in ("itemid", "item_id", "goods_id", "goodsid"):
        if name in required_lower:
            return name
    return None


def detail(item, spec):
    if not spec or not spec.get("path"):
        return {
            "search_item": item,
            "called": False,
            "reason": "official Taobao detail interface was not discovered from current docs",
        }

    method = (spec.get("method") or "").upper()
    if method != "GET":
        return {
            "search_item": item,
            "called": False,
            "reason": f"documented detail method is {method or 'unknown'}; this probe only calls documented GET interfaces",
        }

    id_param = documented_id_parameter(spec.get("required"))
    if not id_param:
        return {
            "search_item": item,
            "called": False,
            "reason": f"no recognized product ID parameter in documented required params: {spec.get('required')}",
        }

    params = {"apikey": API_KEY, id_param: item["id"]}
    try:
        response = requests.get(endpoint_url(spec["path"]), params=params, timeout=TIMEOUT)
        try:
            body = response.json()
        except Exception:
            body = None
        goods = [normalize(x) for x in find_goods(body)]
        text = json.dumps(body, ensure_ascii=False) if body is not None else response.text
        terms = ["AD653C", "2C1A", "65W", "灰色", "单体", "三口", "多口"]
        return {
            "search_item": item,
            "called": True,
            "documented_heading": spec.get("heading"),
            "documented_path": spec.get("path"),
            "documented_id_parameter": id_param,
            "http": response.status_code,
            "code": pick(body, "code", "status"),
            "msg": pick(body, "msg", "message"),
            "normalized_goods": goods[:5],
            "term_hits": {term: term.lower() in text.lower() for term in terms},
            "response_preview": redact(text)[:4000],
        }
    except Exception as exc:
        return {
            "search_item": item,
            "called": True,
            "documented_heading": spec.get("heading"),
            "documented_path": spec.get("path"),
            "error": redact(f"{type(exc).__name__}: {exc}"),
        }


def main():
    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "stage": "haodanku-taobao-exact-product-detail-safe-discovery",
        "target": "CUKTECH/酷态科 AD653C 65W 2C1A 老款方形充电器，灰色单体版",
        "secret_present": bool(API_KEY),
        "secret_value_logged": False,
        "official_docs": None,
        "searches": [],
        "candidate_count": 0,
        "details": [],
        "notes": [
            "Taobao search/detail interface definitions are discovered from Haodanku official docs at runtime.",
            "No conversion, promotion-link, order, or purchase-link endpoint is called.",
            "The result file is written even when docs or API calls fail.",
        ],
    }

    try:
        if not API_KEY:
            report["fatal_error"] = "HAODANKU_API_KEY is not available to this workflow."
            return_code = 0
        else:
            docs = load_taobao_docs()
            report["official_docs"] = docs
            searches = [search(keyword, docs.get("search")) for keyword in KEYWORDS]
            report["searches"] = searches

            seen = set()
            candidates = []
            for result in searches:
                for item in result.get("candidates", []):
                    item_id = item.get("id")
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        candidates.append(item)

            report["candidate_count"] = len(candidates)
            report["details"] = [detail(item, docs.get("detail")) for item in candidates[:5]]
            return_code = 0
    except Exception as exc:
        report["unexpected_error"] = redact(f"{type(exc).__name__}: {exc}")
        return_code = 0
    finally:
        with open("haodanku-probe-result.json", "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return return_code


if __name__ == "__main__":
    sys.exit(main())
