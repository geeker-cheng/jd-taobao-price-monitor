# JD + Taobao/Tmall Price Monitor

A configuration-driven price collection and history project for JD and Taobao/Tmall. Pinduoduo is intentionally out of scope.

## Current behavior

- **JD**: Maishou search/detail. Verified mappings can produce `EXACT_SKU_PRICE`.
- **Taobao/Tmall**: Haodanku ordinary OpenAPI. Current target is recorded as `PRODUCT_PAGE_PRICE` because the API cannot prove the exact variant.
- Price alerts are **not implemented** in the current phase. `alert.enabled` must remain `false`.
- Large price moves are not rejected merely because the percentage change is large; product/source identity validation is the trust boundary.

## Runtime flow

```text
schedule / manual workflow
        ↓
validate config + unit tests
        ↓
collect every MONITORING product
        ↓
JD → Maishou     Taobao/Tmall → Haodanku
        ↓
product / store / mapping validation
        ↓
normalize Quote + confidence
        ↓
update latest status + source health
        ↓
append history only when the logical price sample changes
        ↓
commit data/*.json back to main
```

One platform failure does not stop the other platform. Source/API failures are recorded as errors and are never converted into fake prices.

## Schedule

The production workflow runs at **10:15, 14:15, 18:15 and 22:15 (UTC+8)** every day. GitHub cron uses UTC:

```yaml
15 2,6,10,14 * * *
```

The workflow has `timeout-minutes: 5`, a single concurrency group, no `push` trigger, and therefore state commits do not recursively trigger another run.

Manual `workflow_dispatch` is still available. `run_live=false` performs validation/tests only; `run_live=true` also collects and persists live state.

## State files

```text
data/price_status.json   latest product state and freshness
data/price_history.json  accepted logical price changes, max history_limit samples/product
data/source_health.json  source success/error timestamps and consecutive failures
data/alert_state.json    reserved alert interface only
```

`history_limit` is a **sample-count limit**, not a day count. Repeated checks at the same logical price do not duplicate the history row, although latest status/source-health freshness is updated.

Corrupt JSON state fails closed: the run stops rather than silently overwriting history.

## Current AD653C mapping

JD canonical SKU:

```text
100068768088
```

Verified Maishou-side stable identity:

```text
3nmugCitgMCAZO0wcs
```

The Maishou identity is not a public JD SKU. Full Maishou `goodsId` prefixes have changed between runs, so runtime pins the verified `jdGoodsIdB` and only recovers that same identity. Evidence is documented in `docs/JD_MAPPING.md`.

The Taobao/Tmall target is restricted to `CUKTECH酷态科旗舰店`, but remains `PRODUCT_PAGE_PRICE` until exact-variant evidence is available.

## Add products

Use `config/products.example.yaml` and follow `docs/PRODUCT_ONBOARDING.md`. A new product should remain `NEW` until its identity, store and requested variant are manually verified; then switch it to `MONITORING`.

## API credentials

Taobao/Tmall requires the repository Actions secret:

```text
HAODANKU_API_KEY
```

Do not commit that key.

For JD, the project includes the public default Maishou invite code:

```text
6110440
```

It was found in public third-party integrations and may belong to another party/referral relationship. It is not owned by this repository or its maintainer and does not imply endorsement. Users can override it with `MAISHOU_INVITE_CODE`. The monitor does not need Maishou purchase/share-link conversion endpoints.

## Development checks

```bash
python -m price_monitor.cli validate
python -m unittest discover -s tests -v
```

The workflow runs both checks before every live collection.
