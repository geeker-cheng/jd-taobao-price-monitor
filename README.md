# JD + Taobao/Tmall Price Monitor

A configuration-driven price collection and history framework for personal shopping research.

Current platform support:

- **JD**: Maishou search/detail
- **Taobao/Tmall**: Haodanku ordinary OpenAPI search/detail

**Pinduoduo is intentionally out of scope.**

## Current scope

The current production phase focuses on **reliable collection, identity validation, normalized state, and price history**.

Implemented now:

1. Add products through `config/products.yaml` rather than platform-specific Python changes.
2. Verify a product once before normal monitoring.
3. Never automatically treat the cheapest search result as the requested SKU.
4. Distinguish `EXACT_SKU_PRICE`, `PRODUCT_PAGE_PRICE`, and `UNVERIFIED`.
5. Treat API/network/identity failures as data errors rather than price changes.
6. Persist accepted positive prices from `OK` quotes regardless of the size of the price move.
7. Keep GitHub-hosted-runner state in small JSON files rather than SQLite.

Not implemented in the current phase:

- target-price notifications
- significant-drop notifications
- alert re-arm/state-machine logic
- price-change-based anomaly thresholds

The alert-related config/type/state interfaces are intentionally retained so this layer can be developed later without redesigning the collector. See `docs/CURRENT_SCOPE.md`.

## Product lifecycle

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

Supported lifecycle values: `NEW`, `VERIFIED`, `MONITORING`, `PAUSED`, `INVALID`.

If a product disappears, the system must not silently replace it with a similar result.

## Adding another product

Add one block to `config/products.yaml`. For JD, prefer a canonical JD SKU URL/ID. For Taobao/Tmall, configure the intended brand store plus strict inclusion/exclusion rules.

After editing configuration:

```bash
python -m price_monitor.cli validate
python -m unittest discover -s tests -v
```

Only switch a product to `MONITORING` after identity and store verification.

## Price confidence

- `EXACT_SKU_PRICE`: the source-to-SKU mapping has been explicitly verified.
- `PRODUCT_PAGE_PRICE`: the correct product page/store is known, but the source does not expose enough variant attributes to prove the exact SKU.
- `UNVERIFIED`: the result has not been promoted to exact-SKU confidence.

Confidence is stored in history so a future notification layer can apply different policies without recollecting historical data.

## Current AD653C baseline

### JD

Canonical JD SKU:

```text
100068768088
```

Required shop:

```text
CUKTECH酷态科京东自营旗舰店
```

Exact mapping evidence is documented in `docs/JD_MAPPING.md`.

Current Maishou-side mapping:

```yaml
source:
  mapping:
    verified: true
    provider_goods_id_b: 3nmugCitgMCAZO0wcs
    provider_goods_id: null
```

`provider_goods_id_b` is a Maishou-side opaque/stable-ish identity, **not a public JD SKU**. Full Maishou `goodsId` prefixes changed across live runs, so the runtime pins the stable identity and revalidates title, shop, and self-operated status.

If the cached request handle becomes stale for a non-network reason, the monitor performs at most one bounded discovery query and accepts only the same verified stable identity. It never substitutes another cheaper candidate.

If the identity cannot be recovered, the result is `MAPPED_ENTITY_NOT_FOUND`. If the request is uncertain because of network failure, the result is `SOURCE_ERROR`. Neither state records a price sample.

### Taobao/Tmall

Haodanku can identify `CUKTECH酷态科旗舰店` and the 65W GaN multi-port product page. The detail endpoint does not expose enough variant attributes to prove `AD653C / 2C1A / 灰色 / 单体` on every run, so the quote is deliberately classified as `PRODUCT_PAGE_PRICE`.

## Maishou invite-code disclosure

Taobao/Tmall requires repository secret:

```text
HAODANKU_API_KEY
```

This credential must not be committed.

JD uses the following public Maishou invite code as a reproducible default:

```text
6110440
```

Disclosure:

- `6110440` was found in public third-party Maishou-related integrations and passed the tested Maishou invite/login gate.
- It is not owned by this repository or its maintainer and may be a referral/attribution code belonging to another party.
- The project does not claim endorsement by Maishou or the code owner.
- The monitor uses search/detail endpoints only; it does not need a purchase/share-link conversion endpoint.
- Users can override it with `MAISHOU_INVITE_CODE`.

Override priority:

```text
explicit constructor value
        ↓
MAISHOU_INVITE_CODE environment variable / Actions secret
        ↓
public default 6110440
```

Maishou interfaces used here appear application-facing rather than a guaranteed public developer API and may change without notice.

## State files

```text
data/price_status.json
data/price_history.json
data/alert_state.json
```

- `price_status.json`: latest normalized result for every monitored product.
- `price_history.json`: accepted positive price samples, including confidence/source metadata.
- `alert_state.json`: **reserved extension state only**; current runtime does not maintain target/re-arm/reference alert state.

A sample is accepted into history when the normalized quote is `OK` and has a positive monitoring price. There is intentionally **no default percentage-change anomaly rejection**. Trust is determined by source/product/store identity validation rather than an arbitrary price-movement threshold.

## Reserved alert interface

The following interfaces remain available but are inactive:

```yaml
alert:
  enabled: false
  target_price: null
  significant_drop_pct: null
```

The `AlertEvent` type, `events` output field, and `alert_state.json` are also retained. The current runtime always emits no price alerts. A later notification phase can implement these interfaces separately from price collection.

## GitHub Actions

The workflow is still manual-only:

```text
workflow_dispatch
```

There is no `push` trigger and no schedule. The job has a hard limit:

```yaml
timeout-minutes: 5
```

`run_live=false` performs config validation and unit tests only.

`run_live=true` additionally performs live collection and uploads the three state JSON files as a short-lived artifact.

Automatic scheduling and repository state commits should be enabled only after the persistence design is finalized.
