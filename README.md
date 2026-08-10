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

Earlier Maishou smoke tests found multiple self-operated provider entities with different prices for the same human-facing product. Therefore the production config deliberately leaves:

```yaml
source:
  mapping:
    verified: false
    provider_goods_id: null
```

The runtime will return `AMBIGUOUS_SOURCE_MAPPING` rather than picking the cheapest provider entity. Once an exact Maishou-provider → JD-SKU mapping is verified, pin it in config and set `verified: true`.

### Taobao/Tmall

Haodanku ordinary API can identify:

```text
CUKTECH酷态科旗舰店
```

and the 65W GaN multi-port product page. However the detail endpoint does not expose enough fields to prove `AD653C / 2C1A / 灰色 / 单体` on every run, so the source is deliberately classified as:

```text
PRODUCT_PAGE_PRICE
```

## Secrets

Repository Actions secrets:

```text
HAODANKU_API_KEY
MAISHOU_INVITE_CODE
```

`HAODANKU_API_KEY` is required for Taobao/Tmall.

`MAISHOU_INVITE_CODE` is required for JD. The production code intentionally has **no hard-coded public/referral invite-code fallback**. Do not commit either value into the repository.

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
