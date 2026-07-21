# core-side-patch

This directory is NOT part of the satellite application. It contains
the small patch intended to be applied to CompliVibe core so that it
can (a) accept already-signed, already-verified propagation records
and vendor-risk findings pushed from this satellite, and (b) expose
read-only export endpoints the satellite polls for `consent_records`
and `registered_processors`.

**Status: unverified against real core source.** No core repository or
read-only clone was available in this build environment (see
`../ASSUMPTIONS.md`). These files are written defensively — the
migration inspects the live schema at migration time rather than
assuming a column is absent — but the assumed table/endpoint shapes
themselves have not been checked against production core code.

## Boundary rule enforced here

Core receives only already-signed, already-verified records. It never
imports `cryptography`'s Ed25519 signing primitives or holds a private
key. If core chooses to *independently re-verify* a record's signature
(recommended — "satellite computes and signs; it never decides what
core does with a verified result" — core re-verifies before acting),
that verification logic belongs here, in `routes/patent_ingest_p6.py`,
as a self-contained stub — not as a new dependency pulled into core's
main application.

## Files

- `migrations/0001_consent_propagation_records.py` — dual-path: checks
  whether `consent_records` already has a `propagation_status`
  equivalent column before adding one. Extends the existing table,
  does not duplicate it.
- `migrations/0002_registered_processors.py` — adds the
  `registered_processors` table to core if core does not already have
  an equivalent processor registry.
- `routes/patent_ingest_p6.py` — the two endpoints this satellite's
  `CorePushClient` calls: propagation record ingest and vendor-risk
  finding ingest. Independently re-verifies the record's signature
  against the org's already-known-to-core public key before writing
  anything — it never trusts the satellite's own claim of validity.
