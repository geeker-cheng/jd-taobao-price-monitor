import json
import sys
from datetime import datetime, timezone

import requests

BASE_URL = "https://appapi.maishou88.com"
PUBLIC_INVITE_CODE = "6110440"
CONNECT_TIMEOUT = 6
READ_TIMEOUT = 10
HEADERS = {
    "Accept": "application/json",
    "Referer": "https://hnbc018.kuaizhan.com/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537 Chrome/143 Safari/537",
}

CASES = [
    (1, "taobao", "小米手环"),
    (2, "jd", "iPhone 16"),
    (3, "pdd", "纸巾"),
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
    return bool(set(item.keys()) & {"goodsId", "goods_id", "title", "goodsName", "actualPrice", "price", "shopName"})


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


def call_search(source_type, keyword, invite_code):
    payload = {
        "keyword": keyword,
        "sourceType": str(source_type),
        "page": "1",
        "pageSize": "5",
        "inviteCode": invite_code,
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
    goods = find_goods_list_deep(body)
    first = summarize_first(goods)
    return {
        "http": response.status_code,
        "api_status": body.get("status") if isinstance(body, dict) else None,
        "api_code": body.get("code") if isinstance(body, dict) else None,
        "api_message": body.get("message") if isinstance(body, dict) else None,
        "goods_count": len(goods),
        "first": first,
        "ok": response.status_code == 200 and bool(goods) and bool(first) and first.get("actualPrice") not in (None, "", 0, "0", "0.0"),
        "raw_preview": response.text[:800],
    }


def safe_call(source_type, keyword, invite_code):
    try:
        return call_search(source_type, keyword, invite_code)
    except Exception as exc:
        return {
            "http": None,
            "api_status": None,
            "api_code": None,
            "api_message": None,
            "goods_count": 0,
            "first": None,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main():
    results = []
    for source_type, platform, keyword in CASES:
        print(f"\n===== {platform} / sourceType={source_type} / {keyword} =====")
        with_code = safe_call(source_type, keyword, PUBLIC_INVITE_CODE)
        without_code = safe_call(source_type, keyword, "")
        print("WITH_6110440", json.dumps(with_code, ensure_ascii=False, indent=2))
        print("WITHOUT_CODE", json.dumps(without_code, ensure_ascii=False, indent=2))
        results.append({
            "platform": platform,
            "sourceType": source_type,
            "keyword": keyword,
            "with_6110440": with_code,
            "without_code": without_code,
        })

    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "/api/v1/homepage/searchList",
        "public_invite_code": PUBLIC_INVITE_CODE,
        "results": results,
    }
    with open("smoke-result.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n===== SUMMARY =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
