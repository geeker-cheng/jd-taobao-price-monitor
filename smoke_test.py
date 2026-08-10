# Triggered after GitHub registered the workflow.
import json
import sys
from datetime import datetime, timezone

import requests

BASE_URL = "https://appapi.maishou88.com"
INVITE_CODE = "6110440"  # Public third-party code used only for smoke testing.
KEYWORD = "iPhone 16"
TIMEOUT_SECONDS = 20
HEADERS = {
    "Accept": "application/json",
    "Referer": "https://hnbc018.kuaizhan.com/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537 Chrome/143 Safari/537",
    "Content-Type": "application/json",
}
PLATFORMS = {
    1: "taobao",
    2: "jd",
    3: "pdd",
}


def parse_goods_list(payload):
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    candidates = [data.get("goodsList"), data.get("list"), data.get("items")]
    result = data.get("result")
    if isinstance(result, dict):
        candidates.extend([result.get("goodsList"), result.get("list"), result.get("items")])

    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return candidate
    return []


def pick(item, *keys):
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def request_json(url, payload):
    response = requests.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT_SECONDS)
    text = response.text
    try:
        body = response.json()
    except Exception:
        body = None
    return response.status_code, text, body


def test_platform(source_type, platform):
    result = {
        "platform": platform,
        "sourceType": source_type,
        "search_http": None,
        "search_ok": False,
        "goods_count": 0,
        "goods_id": None,
        "title": None,
        "search_actual_price": None,
        "search_original_price": None,
        "search_coupon_price": None,
        "detail_http": None,
        "detail_ok": False,
        "detail_actual_price": None,
        "detail_original_price": None,
        "detail_coupon_price": None,
        "error": None,
    }

    search_payload = {
        "keyword": KEYWORD,
        "sourceType": str(source_type),
        "inviteCode": INVITE_CODE,
        "supplierCode": "",
        "activityId": "",
        "usageScene": 5,
        "page": 1,
        "pageSize": 5,
    }

    try:
        status, raw, body = request_json(BASE_URL + "/api/v3/goods/list", search_payload)
        result["search_http"] = status
        print(f"\n===== {platform} / sourceType={source_type} =====")
        print("SEARCH_HTTP", status)
        print("SEARCH_RAW", raw[:1500])

        goods = parse_goods_list(body)
        result["goods_count"] = len(goods)
        if not goods:
            result["error"] = "search returned no parseable goods"
            return result

        first = goods[0]
        goods_id = pick(first, "goodsId", "id", "goods_id")
        result["goods_id"] = str(goods_id) if goods_id is not None else None
        result["title"] = pick(first, "title", "goodsName", "name")
        result["search_actual_price"] = pick(first, "actualPrice", "price", "actual_price")
        result["search_original_price"] = pick(first, "originalPrice", "original_price")
        result["search_coupon_price"] = pick(first, "couponPrice", "coupon_price")
        result["search_ok"] = status == 200 and goods_id is not None

        print("PARSED_FIRST", json.dumps({
            "goods_id": result["goods_id"],
            "title": result["title"],
            "actualPrice": result["search_actual_price"],
            "originalPrice": result["search_original_price"],
            "couponPrice": result["search_coupon_price"],
        }, ensure_ascii=False))

        if goods_id is None:
            result["error"] = "first search item has no goods id"
            return result

        detail_payload = {
            "goodsId": str(goods_id),
            "sourceType": str(source_type),
            "inviteCode": INVITE_CODE,
            "keyword": "",
            "usageScene": 5,
            "supplierCode": "",
            "activityId": "",
            "isShare": "0",
            "token": "",
        }
        d_status, d_raw, d_body = request_json(BASE_URL + "/api/v3/goods/detail", detail_payload)
        result["detail_http"] = d_status
        print("DETAIL_HTTP", d_status)
        print("DETAIL_RAW", d_raw[:1500])

        detail = d_body.get("data") if isinstance(d_body, dict) else None
        if not isinstance(detail, dict) or not detail:
            result["error"] = "detail returned no parseable data"
            return result

        result["detail_actual_price"] = pick(detail, "actualPrice", "price", "actual_price")
        result["detail_original_price"] = pick(detail, "originalPrice", "original_price")
        result["detail_coupon_price"] = pick(detail, "couponPrice", "coupon_price")
        result["detail_ok"] = d_status == 200 and result["detail_actual_price"] not in (None, "", 0, "0", "0.0")

        return result
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
        "all_search_ok": all(r["search_ok"] for r in results),
        "all_detail_ok": all(r["detail_ok"] for r in results),
    }

    with open("smoke-result.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n===== SUMMARY =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # The workflow should complete even when the third-party API itself fails;
    # the result file and logs are the smoke-test evidence.
    return 0


if __name__ == "__main__":
    sys.exit(main())
