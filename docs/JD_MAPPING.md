# JD exact mapping: AD653C / SKU 100068768088

Verified on: 2026-08-10

This document records why the production monitor maps canonical JD SKU
`100068768088` to Maishou-side identity `3nmugCitgMCAZO0wcs`.

## Canonical product

Target:

- Brand: CUKTECH / 酷态科
- Model: AD653C
- Power: 65W
- Ports: 2C1A
- Form: old square/traditional block
- Package: standalone charger
- Color target: gray
- JD SKU: `100068768088`

Independent public records repeatedly tie `100068768088` to AD653C / 65W /
2C1A. A JD-backed procurement mirror for `/detail/jd/100068768088` currently
shows this exact title:

```text
CUKTECH酷态科65W氮化镓充电头USB/Type-C多口快充器适用40W苹果17小米/华为/三星/MacbookNeo/笔记本电脑
```

It also reports the package as one charger plus one manual.

Sources used for the 2026-08-10 verification:

- https://mall.icw.buaa.edu.cn/SzhtShop/detail/jd/100068768088
- https://www.zhizhizhi.com/n/cferz
- https://www.zhizhizhi.com/n/d9boh
- https://www.jd.com/jiage/9987347e9857ec8d8d6d.html?brand=CUKTECH

The historical deal pages link directly to `item.jd.com/100068768088.html`
and identify the product as AD653C / 65W / 2C1A. They repeatedly record a
JD page/activity price around CNY 78 before account/coupon-specific discounts.

## Maishou candidates

The live Maishou detail probe returned three self-operated candidates from
`CUKTECH酷态科京东自营旗舰店`.

### Candidate A

```text
jdGoodsIdB: 3xcjcDDVDGKSVJmQFn
price seen: 86.2
title:
CUKTECH酷态科65W氮化镓充电器多口Type-C快充头兼容40W适用小米苹果17手机/ipad/MacBookNeo笔记本电脑
```

Current JD category/search indexes expose this title as a separate 65W
self-operated listing with a different review-count bucket from the canonical
title. It is therefore not selected for SKU `100068768088`.

### Candidate B — selected

```text
jdGoodsIdB: 3nmugCitgMCAZO0wcs
price seen: 77.7
title:
CUKTECH酷态科65W氮化镓充电头USB/Type-C多口快充器适用40W苹果17小米/华为/三星/MacbookNeo/笔记本电脑
```

This title matches the independently resolved canonical SKU title exactly.
It is therefore the strongest evidence-backed Maishou identity for
`100068768088`.

### Candidate C

```text
jdGoodsIdB: 391fhWgEXxrB4zqSXI
price seen: 78.0
title:
CUKTECH酷态科65W氮化镓充电头USB/Type-C多口快充器适用40W苹果17小米/华为/MacbookNeo笔记本
```

This is very close to the canonical title but is abbreviated and no direct
public canonical-SKU evidence was found for this exact title. It is therefore
not selected merely because its price is close to historical CNY 78 records.

## Why `jdGoodsIdB` is used instead of full `goodsId`

Two successful live runs showed that the returned full Maishou `goodsId`
prefix can change while the trailing/stable `jdGoodsIdB` remains the same.

Example for Candidate B:

```text
earlier request handle:
Jx8CO9GFGZU2AFBTBo432AFBTBo438_3nmugCitgMCAZO0wcs

later returned goodsId:
Jx8AO9GFGZU2AF1LELXw2AFBTBo438_3nmugCitgMCAZO0wcs

stable identity:
3nmugCitgMCAZO0wcs
```

Therefore:

- `100068768088` remains the canonical public JD SKU.
- `3nmugCitgMCAZO0wcs` is only a Maishou-side stable-ish mapping identity.
- Full `goodsId` strings are request handles/cache hints, not durable identity.

## Runtime safety rule

The production adapter may promote a JD quote to `EXACT_SKU_PRICE` only when:

1. the configured mapping is explicitly verified;
2. the returned Maishou stable identity equals `3nmugCitgMCAZO0wcs`;
3. the title still passes target-family checks;
4. the shop still matches the configured JD self-operated flagship store;
5. self-operated status is still present.

If the cached full `goodsId` becomes stale for a non-network reason, the
adapter may perform one bounded discovery query, but it may recover only the
same verified `jdGoodsIdB`.

It must never substitute Candidate A, Candidate C, or any newly cheaper search
result merely because the verified entity is unavailable.

If the verified stable identity cannot be recovered, return
`MAPPED_ENTITY_NOT_FOUND`. If the request is uncertain because of a transport
failure, return `SOURCE_ERROR`.

## Revalidation caveat

Maishou endpoints used here are application-facing third-party interfaces and
their identifiers or semantics may change. This mapping should be revalidated
if the title, shop, stable ID, package identity, or source behavior changes.
