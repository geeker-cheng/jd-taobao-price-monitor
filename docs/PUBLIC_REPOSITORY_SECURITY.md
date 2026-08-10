# Public repository security

This repository is intended to remain public.

## Secrets

Never commit real credentials. Runtime credentials belong in GitHub Actions Secrets, including:

- `HAODANKU_API_KEY`
- a private/custom `MAISHOU_INVITE_CODE`, if one is used

The documented default Maishou invite code `6110440` is intentionally public and is not treated as a private credential.

## Runtime protection

Live source errors can contain request URLs. Some APIs place credentials in query/path parameters, so the monitor applies two protections before public state is committed:

1. Recursive redaction of known environment secret values and sensitive fields/URL parameters.
2. A `scan-state` workflow gate that inspects all public `data/*.json` files after collection and before `git commit`.

If the gate detects material that would be redacted, the workflow fails and refuses to commit the state snapshot.

GitHub's log masking is not considered sufficient protection because files committed to a public repository are outside log masking.
