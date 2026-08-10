# Current production scope

Implemented:

- JD collection through Maishou with verified stable mapping support.
- Taobao/Tmall collection through Haodanku.
- Product/store/variant-family validation.
- `EXACT_SKU_PRICE`, `PRODUCT_PAGE_PRICE`, and `UNVERIFIED` confidence.
- Persistent latest status, deduplicated price-change history, and source health.
- Scheduled GitHub Actions with repository state commits.
- Per-source failure isolation, hard workflow timeout, and concurrency protection.

Not implemented:

- Target-price alerts.
- Significant-drop alerts.
- ChatGPT/email/webhook price notifications.
- Price-change anomaly rejection.

The `alert` configuration and related Python types remain reserved interfaces only and must stay disabled.
