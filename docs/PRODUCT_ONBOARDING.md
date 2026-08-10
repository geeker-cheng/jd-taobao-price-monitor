# Product onboarding

The monitor is configuration-driven. New products should normally require only `config/products.yaml` changes.

## JD

1. Add the canonical JD product URL and public SKU.
2. Record the exact requested variant and allowed self-operated store.
3. Configure strict required/excluded title terms.
4. Discover Maishou candidates.
5. Verify the Maishou stable identity (`jdGoodsIdB`) against the canonical JD SKU with independent evidence.
6. Set `source.mapping.verified: true` only after verification.
7. Change lifecycle status to `MONITORING`.

A missing verified entity must never be silently replaced by a cheaper similar product.

## Taobao/Tmall

1. Record the exact requested variant and official/flagship store.
2. Configure strict search terms and title exclusions.
3. Validate the Haodanku product page and store.
4. Keep confidence at `PRODUCT_PAGE_PRICE` unless an API can prove the exact SKU/variant.
5. Change lifecycle status to `MONITORING` after manual confirmation.

## Validation

Run before enabling a product:

```bash
python -m price_monitor.cli validate
python -m unittest discover -s tests -v
```

Use `config/products.example.yaml` as the starting template.
