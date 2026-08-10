import json
import sys
import time
from datetime import datetime, timezone

import requests

BASE_URL = "https://appapi.maishou88.com"
PUBLIC_INVITE_CODE = "6110440"
CONNECT_TIMEOUT = 6
READ_TIMEOUT = 12
HEADERS = {
    "Accept": "application/json",
    "Referer": "https://hnbc018.kuaizhan.com/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537 Chrome/143 Safari/537",
}

# Target confirmed by the user:
# CUKTECH / 酷态科 AD653C 65W GaN charger, old square 2C1A model,
# standalone charger only. Explicitly exclude newer mini / Ultra / card-style
# products and bundles.
TARGET = {
    "brand_terms": ["酷态科", "cuktech"],
    "exact_model_terms": ["ad653c"],
    "power_terms": ["65w", "65瓦"],
    "interface_terms": ["2c1a", "三口", "多口"],
    "excluded_terms": [
        "mini", "ultra", "屏显", "卡片", "电能卡片", "电能片",
        "90w", "100w", "套装", "套餐", "数据线", "充电线", "电池",
    ],
}

CASES = [
    (1, "taobao", ["酷态科 AD653C", "CUKTECH AD653C", "酷态科 65W 2C1A", "酷态科 65W 氮化镓"]),
    (2, "jd", ["酷态科 AD653C", "CUKTECH AD653C", "酷态科 65W 2C1A", "酷态科 65W 氮化镓"]),
    (3, "pdd", ["酷态科 AD653C", "CUKTECH AD653C", "酷态科 65W 2C1A", "酷态科 65W 氮化镓"]),
]


def pick(item, *keys):
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def looks_like_goods(item):
    if not isinstance(item, dict):
        return False
    return bool(set(item.keys()) & {
        "goodsId", "goods_id", "title", "goodsName", "actualPrice", "price", "shopName"
    })


def find_goods_list_deep(obj):
    if isinstance(obj, list):
        if obj and any(looks_like_goods(x) for x in obj):
            return [x for x in obj if isinstance(x, dict)]
        for value in obj:
            found = find_goods_list_deep(value)
            if found:
                return found
    elif isinstance(obj, dict):
        for value in obj.values():
            found = find_goods_list_deep(value)
            if found:
                return found
    return []


def normalize_goods(item):
    return {
        "goods_id": pick(item, "goodsId", "id", "goods_id"),
        "title": pick(item, "title", "goodsName", "name"),
        "shopName": pick(item, "shopName", "shop_name"),
        "platformName": pick(item, "platformName", "platform_name"),
        "actualPrice": pick(item, "actualPrice", "price", "actual_price"),
        "originalPrice": pick(item, "originalPrice", "original_price"),
        "couponPrice": pick(item, "couponPrice", "coupon_price"),
        "sourceType": pick(item, "sourceType", "source_type"),
    }


def compact(text):
    return (text or "").lower().replace(" ", "").replace("-", "")


def contains_any(text, terms):
    value = compact(text)
    return any(compact(term) in value for term in terms)


def product_matches(goods):
    title = goods.get("title") or ""
    value = compact(title)
    brand_ok = contains_any(title, TARGET["brand_terms"])
    exact_model = contains_any(title, TARGET["exact_model_terms"])
    descriptive_model = (
        contains_any(title, TARGET["power_terms"])
        and contains_any(title, TARGET["interface_terms"])
    )
    excluded = contains_any(title, TARGET["excluded_terms"])
    return brand_ok and (exact_model or descriptive_model) and not excluded


def store_matches(platform, goods):
    shop = compact(goods.get("shopName") or "")
    if not shop:
        return False
    brand_ok = "酷态科" in shop or "cuktech" in shop
    if platform == "jd":
        return "自营" in shop or (brand_ok and "旗舰店" in shop)
    return brand_ok and ("旗舰店" in shop or "官方" in shop)


def eligible(platform, goods):
    return product_matches(goods) and store_matches(platform, goods)


def call_search(source_type, keyword):
    payload = {
        "keyword": keyword,
        "sourceType": str(source_type),
        "page": "1",
        "pageSize": "20",
        "inviteCode": PUBLIC_INVITE_CODE,
    }
    response = requests.post(
        BASE_URL + "/api/v1/homepage/searchList",
        headers=HEADERS,
        data=payload,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )
    try:
        body = response.json()
    except Exception:
        body = None
    goods = [normalize_goods(x) for x in find_goods_list_deep(body)]
    return {
        "http": response.status_code,
        "api_status": body.get("status") if isinstance(body, dict) else None,
        "api_code": body.get("code") if isinstance(body, dict) else None,
        "api_message": body.get("message") if isinstance(body, dict) else None,
        "goods_count": len(goods),
        "goods": goods,
        "raw_preview": response.text[:500],
    }


def safe_call(source_type, keyword):
    try:
        return call_search(source_type, keyword)
    except Exception as exc:
        return {
            "http": None,
            "api_status": None,
            "api_code": None,
            "api_message": None,
            "goods_count": 0,
            "goods": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def main():
    platform_results = []

    for source_type, platform, keywords in CASES:
        print(f"\n===== {platform} / sourceType={source_type} =====")
        seen = set()
        all_goods = []
        attempts = []

        for keyword in keywords:
            result = safe_call(source_type, keyword)
            attempts.append({
                "keyword": keyword,
                "http": result.get("http"),
                "api_status": result.get("api_status"),
                "api_code": result.get("api_code"),
                "api_message": result.get("api_message"),
                "goods_count": result.get("goods_count", 0),
                "error": result.get("error"),
            })
            for item in result.get("goods", []):
                key = str(item.get("goods_id") or "") + "|" + str(item.get("title") or "")
                if key not in seen:
                    seen.add(key)
                    all_goods.append(item)
            print("ATTEMPT", json.dumps(attempts[-1], ensure_ascii=False))

            current_eligible = [x for x in all_goods if eligible(platform, x)]
            if current_eligible:
                break
            time.sleep(0.4)

        product_candidates = [x for x in all_goods if product_matches(x)]
        eligible_matches = [x for x in all_goods if eligible(platform, x)]

        print("PRODUCT_CANDIDATES", json.dumps(product_candidates, ensure_ascii=False, indent=2))
        print("ELIGIBLE_MATCHES", json.dumps(eligible_matches, ensure_ascii=False, indent=2))

        platform_results.append({
            "platform": platform,
            "sourceType": source_type,
            "attempts": attempts,
            "unique_goods_count": len(all_goods),
            "product_candidates": product_candidates,
            "eligible_matches": eligible_matches,
            "passed": bool(eligible_matches),
        })

    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "/api/v1/homepage/searchList",
        "public_invite_code": PUBLIC_INVITE_CODE,
        "target": "CUKTECH/酷态科 AD653C 65W GaN 2C1A 老款方形充电器，单体",
        "store_requirement": "京东自营或品牌旗舰店；淘宝/拼多多要求酷态科/CUKTECH官方或旗舰店",
        "excluded": "mini / Ultra / 屏显 / 卡片 / 90W / 100W / 套装 / 线材 / 电池",
        "results": platform_results,
    }

    with open("smoke-result.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n===== SUMMARY =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
