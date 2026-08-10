# JD + Taobao/Tmall Price Monitor

A small, configuration-driven price-monitoring framework for personal shopping.

The project currently supports only:

- **JD**: Maishou search/detail as the data source.
- **Taobao/Tmall**: Haodanku ordinary OpenAPI search/detail.

**Pinduoduo is intentionally out of scope.**

## Design goals

1. Adding a product should normally mean editing `config/products.yaml`, not changing Python code.
2. A new product is verified once before it becomes a normal monitored item.
3. Never treat “the cheapest search result” as the requested SKU automatically.
4. Distinguish exact-SKU prices from product-page prices.
5. API failure is a data error, not “no price change”.
6. Sudden suspicious drops are rejected as anomalies instead of immediately triggering an alert.
7. GitHub-hosted runners persist state through small JSON files rather than SQLite.

## Product lifecycle

Recommended onboarding:

```text
NEW
 ↓
parse product link / identifiers
 ↓
verify brand + model + shop + variant
 ↓
human confirmation once
 ↓
VERIFIED
 ↓
MONITORING
```

Supported lifecycle values:

- `NEW`
- `VERIFIED`
- `MONITORING`
- `PAUSED`
- `INVALID`

If a product disappears, the system must not silently replace it with a similar search result.

## Add another product

Add one block to `config/products.yaml`.

For JD, prefer a canonical JD product/SKU URL and ID. For Taobao/Tmall, configure the exact brand store and strict title exclusions. After adding a product, run:

```bash
python -m price_monitor.cli validate
python -m unittest discover -s tests -v
```

A product should only be switched to `MONITORING` after its identity and store are confirmed.

## Price confidence

The normalized output uses:

- `EXACT_SKU_PRICE`: source-to-SKU mapping has been explicitly verified.
- `PRODUCT_PAGE_PRICE`: correct product page/store, but the API does not expose enough variant attributes to prove the exact SKU.
- `UNVERIFIED`: source result cannot yet be promoted to exact-SKU confidence.

By default, `PRODUCT_PAGE_PRICE` does **not** generate a formal target-price alert. It can only create a candidate event that requires SKU confirmation.

## Current AD653C baseline

### JD

Canonical JD SKU:

```text
100068768088
```

Shop requirement:

```text
CUKTECH酷态科京东自营旗舰店
```

The exact SKU mapping investigation is documented in:

```text
docs/JD_MAPPING.md
```

The current verified Maishou-side mapping is:

```yaml
source:
  mapping:
    verified: true
    provider_goods_id_b: 3nmugCitgMCAZO0wcs
    provider_goods_id: null
```

`provider_goods_id_b` is a Maishou-side opaque/stable-ish identity. It is **not** described as a public JD SKU.

Why the full `goodsId` is not pinned:

- Multiple Maishou entities matched the human-facing 65W charger family.
- The full `goodsId` prefix changed between separate live GitHub Actions runs.
- `jdGoodsIdB` remained stable across those runs.
- Independent sources tie JD SKU `100068768088` to the same full title returned by `3nmugCitgMCAZO0wcs`.

Runtime behavior for a verified mapping is deliberately strict:

```text
known candidate for provider_goods_id_b
        ↓
detail request
        ↓
same stable identity + title/shop/self-operated checks
        ↓
EXACT_SKU_PRICE
```

If that cached request handle becomes stale for a non-network reason, the monitor performs at most one discovery search and accepts **only the same verified `provider_goods_id_b`**. It never substitutes another cheaper candidate.

If the verified identity cannot be recovered, the result is:

```text
MAPPED_ENTITY_NOT_FOUND
```

If the request is uncertain because of a network error, the result is:

```text
SOURCE_ERROR
```

Neither state records a price sample.

### Taobao/Tmall

Haodanku ordinary API can identify:

```text
CUKTECH酷态科旗舰店
```

and the 65W GaN multi-port product page. However the detail endpoint does not expose enough fields to prove `AD653C / 2C1A / 灰色 / 单体` on every run, so the source is deliberately classified as:

```text
PRODUCT_PAGE_PRICE
```

## API keys and Maishou invite-code disclosure

Repository Actions secret required for Taobao/Tmall:

```text
HAODANKU_API_KEY
```

`HAODANKU_API_KEY` is a credential and must **not** be committed to the repository.

For JD, the project intentionally includes this public Maishou invite code as a reproducible default:

```text
6110440
```

Important disclosure:

- `6110440` was found in public third-party Maishou-related integrations during this project's research and was verified to pass the currently tested Maishou v1 invite/login gate.
- The code is **not owned by this repository or its maintainer**. It may be a referral/attribution code belonging to another party.
- The project does not claim endorsement by Maishou or by the owner of that invite code.
- The monitor uses Maishou search/detail endpoints for price research. It does not need to call a purchase/share-link conversion endpoint.
- Anyone who wants to avoid third-party referral attribution should configure their own `MAISHOU_INVITE_CODE`.

Override priority is:

```text
explicit constructor value
        ↓
MAISHOU_INVITE_CODE environment variable / GitHub Actions secret
        ↓
public default 6110440
```

Therefore a clone or fork can run JD research with the documented public default, while users with their own invite code can override it without changing source code. `MAISHOU_INVITE_CODE` is optional; `HAODANKU_API_KEY` remains required for Taobao/Tmall.

Maishou endpoints used by this project appear to be application-facing interfaces rather than a guaranteed public developer API, so availability and behavior can change without notice.

## State files

```text
data/price_status.json
data/price_history.json
data/alert_state.json
```

`price_status.json` contains the latest normalized result.

`price_history.json` contains accepted price samples.

`alert_state.json` contains target re-arm state, last valid price and significant-drop reference.

## Alert behavior

### Target price

```text
above target → ARMED
first cross below target → one alert
stay below → no repeated alert
rise above → re-arm
```

### Gradual drop

Significant-drop logic compares against a persistent reference price, not only the previous sample. Therefore a sequence such as:

```text
1000 → 970 → 940 → 910
```

can still trigger an 8% threshold.

`significant_drop_pct` is `null` in the sample products because no user threshold has been chosen yet.

### Anomaly protection

A drop of 25% or more from the last accepted price is rejected as `ANOMALY` by default. It does not move the accepted-price baseline and cannot generate a formal alert.

This threshold is a safety guard and can be changed per product.

## GitHub Actions

The production workflow is intentionally **manual-only** for now:

```text
workflow_dispatch
```

There is no `push` trigger and no schedule.

The job has:

```yaml
timeout-minutes: 5
```

`run_live=false` runs only config validation and unit tests.

`run_live=true` additionally performs a live collection using repository secrets and uploads the resulting state JSON as a short-lived artifact.

Automatic scheduling and state commits should only be enabled after the manual production simulation is reviewed.
