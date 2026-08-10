import json
import sys
from datetime import datetime, timezone

import requests

BASE_URL = "https://appapi.maishou88.com"
INVITE_CODE = "6110440"  # Public third-party code used only for smoke testing.
KEYWORD = "iPhone 16"
TIMEOUT_SECONDS = 20
COMMON_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://hnbc018.kuaizhan.com/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537 Chrome/143 Safari/537",
}
PLATFORMS = {1: "taobao", 2: "jd", 3: "pdd"}


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
    keys = set(item.keys())
    return bool(keys & {"goodsId", "goods_id", "title", "goodsName", "actualPrice", "price", "shopName"})


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


def summarize_first(goods):
    if not goods:
        return None
    first = goods[0]
    return {
        "goods_id": pick(first, "goodsId", "id", "goods_id"),
        "title": pick(first, "title", "goodsName", "name"),
        "actualPrice": pick(first, "actualPrice", "price", "actual_price"),
        "originalPrice": pick(first, "originalPrice", "original_price"),
        "couponPrice": pick(first, "couponPrice", "coupon_price"),
        "shopName": pick(first, "shopName", "shop_name"),
    }


def post_form(url, payload):
    response = requests.post(url, headers=COMMON_HEADERS, data=payload, timeout=TIMEOUT_SECONDS)
    try:
        body = response.json()
    except Exception:
        body = None
    return response.status_code, response.text, body


def post_json(url, payload):
    headers = dict(COMMON_HEADERS)
    headers["Content-Type"] = "application/json"
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    try:
        body = response.json()
    except Exception:
        body = None
    return response.status_code, response.text, body


def test_platform(source_type, platform):
    result = {
        "platform": platform,
        "sourceType": source_type,
        "v1": {"http": None, "ok": False, "goods_count": 0, "first": None, "api_status": None, "api_code": None, "api_message": None},
        "v3": {"http": None, "ok": False, "goods_count": 0, "first": None, "api_status": None, "api_code": None, "api_message": None},
        "error": None,
    }

    print(f"\n===== {platform} / sourceType={source_type} =====")

    try:
        # Current endpoint observed in recently updated public Maishou clients.
        v1_payload = {
            "keyword": KEYWORD,
            "sourceType": str(source_type),
            "page": "1",
            "pageSize": "5",
            "inviteCode": INVITE_CODE,
        }
        status, raw, body = post_form(BASE_URL + "/api/v1/homepage/searchList", v1_payload)
        goods = find_goods_list_deep(body)
        result["v1"].update({
            "http": status,
            "goods_count": len(goods),
            "first": summarize_first(goods),
            "api_status": body.get("status") if isinstance(body, dict) else None,
            "api_code": body.get("code") if isinstance(body, dict) else None,
            "api_message": body.get("message") if isinstance(body, dict) else None,
        })
        first = result["v1"]["first"] or {}
        result["v1"]["ok"] = status == 200 and bool(goods) and first.get("actualPrice") not in (None, "", 0, "0", "0.0")
        print("V1_HTTP", status)
        print("V1_RAW", raw[:2500])
        print("V1_PARSED", json.dumps(result["v1"], ensure_ascii=False))

        # Old endpoint documented by Kumagt/price-monitor, retained for comparison.
        v3_payload = {
            "keyword": KEYWORD,
            "sourceType": str(source_type),
            "inviteCode": INVITE_CODE,
            "supplierCode": "",
            "activityId": "",
            "usageScene": 5,
            "page": 1,
            "pageSize": 5,
        }
        status, raw, body = post_json(BASE_URL + "/api/v3/goods/list", v3_payload)
        goods = find_goods_list_deep(body)
        result["v3"].update({
            "http": status,
            "goods_count": len(goods),
            "first": summarize_first(goods),
            "api_status": body.get("status") if isinstance(body, dict) else None,
            "api_code": body.get("code") if isinstance(body, dict) else None,
            "api_message": body.get("message") if isinstance(body, dict) else None,
        })
        first = result["v3"]["first"] or {}
        result["v3"]["ok"] = status == 200 and bool(goods) and first.get("actualPrice") not in (None, "", 0, "0", "0.0")
        print("V3_HTTP", status)
        print("V3_RAW", raw[:1500])
        print("V3_PARSED", json.dumps(result["v3"], ensure_ascii=False))

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print("ERROR", result["error"])

    return result


def main():
    results = [test_platform(source, name) for source, name in PLATFORMS.items()]
    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "keyword": KEYWORD,
        "invite_code": INVITE_CODE,
        "results": results,
        "all_v1_ok": all(r["v1"]["ok"] for r in results),
        "all_v3_ok": all(r["v3"]["ok"] for r in results),
    }

    with open("smoke-result.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n===== SUMMARY =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
