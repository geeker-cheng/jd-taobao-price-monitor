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
TAOBAO_KEYWORDS = ["酷态科 AD653C", "酷态科 65W 2C1A", "酷态科 65W 氮化镓"]
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
    model = "ad653c" in value or ("65w" in value and ("2c1a" in value or "三口" in value or "多口" in value or "氮化镓" in value))
    return brand and model and not any(compact(term) in value for term in EXCLUDED)


def find_goods(obj):
    found = []
    if isinstance(obj, dict):
        keys = set(obj)
        id_keys = {"itemid", "item_id", "goods_id", "goodsId", "sku_id", "skuId"}
        title_keys = {"itemtitle", "title", "goods_name", "goodsName", "goodsname"}
        if keys & id_keys and keys & title_keys:
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
        "id": pick(item, "itemid", "item_id", "goods_id", "goodsId", "sku_id", "skuId"),
        "title": pick(item, "itemtitle", "title", "goods_name", "goodsName", "goodsname"),
        "shop": pick(item, "shopname", "shop_name", "shopName", "seller_name"),
        "brand": pick(item, "brand_name", "brandName", "brand"),
        "price": pick(item, "itemprice", "price", "actual_price", "actualPrice"),
        "coupon_price": pick(item, "couponmoney", "coupon_price", "couponPrice"),
        "final_price": pick(item, "itemendprice", "end_price", "final_price"),
        "is_tmall": pick(item, "shoptype", "is_tmall", "istmall"),
    }


def response_summary(response):
    try:
        body = response.json()
    except Exception:
        body = None
    goods = [normalized_item(x) for x in find_goods(body)]
    return body, goods, {
        "http": response.status_code,
        "api_code": pick(body, "code", "status") if isinstance(body, dict) else None,
        "api_msg": pick(body, "msg", "message") if isinstance(body, dict) else None,
        "result_count": len(goods),
        "top_results": goods[:10],
        "candidates": [x for x in goods if looks_like_target(x.get("title"))][:10],
        "ok": response.ok and isinstance(body, dict),
    }


def double_encode(value):
    return quote(quote(value, safe=""), safe="")


def call_taobao_supersearch(keyword):
    encoded = double_encode(keyword)
    url = (
        "http://v2.api.haodanku.com/supersearch/"
        f"apikey/{API_KEY}/keyword/{encoded}/back/20/min_id/1/"
        "tb_p/1/sort/0/is_tmall/1/is_coupon/0/limitrate/0"
    )
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        _, _, summary = response_summary(response)
        summary["keyword"] = keyword
        return summary
    except Exception as exc:
        return {
            "keyword": keyword,
            "http": None,
            "api_code": None,
            "api_msg": None,
            "result_count": 0,
            "top_results": [],
            "candidates": [],
            "ok": False,
            "error": redact(f"{type(exc).__name__}: {exc}"),
        }


def section_from_markdown(text, heading):
    pattern = re.compile(rf"^###\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    tail = text[match.end():]
    next_heading = re.search(r"^###\s+", tail, re.MULTILINE)
    section = text[match.start(): match.end() + (next_heading.start() if next_heading else len(tail))]
    return section.strip()


def parse_interface_section(section):
    if not section:
        return None

    def field(label):
        match = re.search(rf"^-\s*{re.escape(label)}：\s*(.+)$", section, re.MULTILINE)
        return match.group(1).strip() if match else None

    return {
        "heading": section.splitlines()[0].lstrip("# ").strip(),
        "permission": field("权限要求"),
        "method": field("请求方式"),
        "path": field("接口路径"),
        "required": field("必填参数"),
        "optional": field("可选参数"),
        "return_fields": field("返回核心字段"),
        "official_doc": (re.search(r"官方文档地址：(https?://\S+)", section).group(1).rstrip("。")
                         if re.search(r"官方文档地址：(https?://\S+)", section) else None),
    }


def download_product_docs():
    result = {"download_ok": False, "http": None, "interfaces": {}}
    try:
        response = requests.get(DOCS_ZIP_URL, timeout=TIMEOUT)
        result["http"] = response.status_code
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            product_name = next(
                name for name in archive.namelist()
                if name.replace("\\", "/").endswith("interfaces/商品接口.md")
            )
            text = archive.read(product_name).decode("utf-8", errors="replace")
            for heading in ["淘宝商品搜索", "京东商品搜索/详情", "拼多多商品搜索/详情"]:
                section = section_from_markdown(text, heading)
                result["interfaces"][heading] = parse_interface_section(section)
            result["download_ok"] = True
    except Exception as exc:
        result["error"] = redact(f"{type(exc).__name__}: {exc}")
    return result


def call_documented_interface(interface, keyword):
    if not interface or not interface.get("path"):
        return {"called": False, "reason": "official interface path not found"}
    method = (interface.get("method") or "").upper()
    if method != "GET":
        return {"called": False, "reason": f"documented method is {method or 'unknown'}, not GET"}

    path = interface["path"].strip()
    if not path.startswith("http://") and not path.startswith("https://"):
        path = "https://" + path.lstrip("/")

    section_text = " ".join(str(interface.get(k) or "") for k in ("required", "optional"))
    params = {"apikey": API_KEY}
    if "keyword" in section_text:
        params["keyword"] = keyword
    if "min_id" in section_text:
        params["min_id"] = 1
    if "back" in section_text:
        params["back"] = 20
    if "sort" in section_text:
        params["sort"] = 0

    try:
        response = requests.get(path, params=params, timeout=TIMEOUT, allow_redirects=True)
        _, _, summary = response_summary(response)
        summary.update({
            "called": True,
            "keyword": keyword,
            "documented_path": interface["path"],
            "documented_permission": interface.get("permission"),
        })
        return summary
    except Exception as exc:
        return {
            "called": True,
            "keyword": keyword,
            "documented_path": interface["path"],
            "documented_permission": interface.get("permission"),
            "http": None,
            "ok": False,
            "error": redact(f"{type(exc).__name__}: {exc}"),
        }


def main():
    if not API_KEY:
        print("ERROR: HAODANKU_API_KEY is not available to this workflow.")
        return 2

    docs = download_product_docs()
    taobao_results = [call_taobao_supersearch(keyword) for keyword in TAOBAO_KEYWORDS]

    jd_interface = docs.get("interfaces", {}).get("京东商品搜索/详情")
    pdd_interface = docs.get("interfaces", {}).get("拼多多商品搜索/详情")

    jd_results = [
        call_documented_interface(jd_interface, "100068768088"),
        call_documented_interface(jd_interface, "酷态科 AD653C"),
    ]
    pdd_results = [
        call_documented_interface(pdd_interface, "酷态科 AD653C"),
        call_documented_interface(pdd_interface, "酷态科 65W 2C1A"),
    ]

    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "stage": "haodanku-platform-permission-and-product-probe",
        "target": "CUKTECH/酷态科 AD653C 65W 2C1A 老款方形充电器，灰色单体版",
        "secret_present": True,
        "secret_value_logged": False,
        "official_docs": docs,
        "taobao": taobao_results,
        "jd": jd_results,
        "pdd": pdd_results,
        "notes": [
            "No affiliate conversion, purchase-link, order, or promotion-link endpoint is called.",
            "JD/PDD paths and parameter names are read from Haodanku's official documentation package at runtime.",
            "The API key is read only from HAODANKU_API_KEY and is never intentionally written to output.",
        ],
    }

    with open("haodanku-probe-result.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
