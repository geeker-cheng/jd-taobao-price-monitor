# Current production scope

Current phase: reliable price collection and state persistence.

Implemented now:

- JD/Taobao product identity validation
- normalized price quotes
- accepted price history
- source confidence levels
- source/network failure states

Reserved for future work, but intentionally inactive now:

- target-price alerts
- significant-drop alerts
- alert re-arm/state-machine logic
- price-change-based anomaly rejection

A large price move by itself is not treated as invalid data. A sample is accepted when the source returns an `OK` quote with a positive monitoring price and the platform-specific identity/store validation has already passed.

The `alert` config block, `AlertEvent` type, `events` output field, and `data/alert_state.json` are retained only as compatibility/extension interfaces. They currently do not produce notifications or reject price samples.
