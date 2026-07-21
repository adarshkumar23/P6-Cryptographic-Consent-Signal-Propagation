# Developer Handoff — P6 Consent Propagation

## What's built and tested

- Ed25519 signing/verification (`app/crypto/signing.py`), tested for
  tamper-detection at the single-byte level, wrong-key rejection, and
  order-independent canonicalization.
- Per-org keypair generation with satellite-local encrypted-at-rest
  private keys and per-org salted subject hashing
  (`app/crypto/keys.py`).
- Consent token emission with a structural (not policy) guarantee that
  the raw data subject identifier never persists anywhere
  (`app/services/token_emitter.py`, enforced by
  `tests/boundary/test_no_raw_identifier_ever_stored.py`).
- Propagation dispatch to all registered processors, recording an
  attempt regardless of outcome (`app/services/propagation_dispatcher.py`).
- Signature-gated acknowledgement acceptance, both the synchronous
  path and the async webhook callback
  (`app/api/routes_webhooks.py`).
- Append-only hash chain with full-chain tamper detection
  (`app/services/chain_builder.py`).
- Three-stage escalation policy: retry backoff → human escalation →
  vendor-risk flag pushed to core (`app/services/escalation_scheduler.py`).
  The scheduler is a pure decision function driven by an external
  cron/worker — it does not itself sleep.
- `core-side-patch/` — a self-contained, unapplied patch intended for
  CompliVibe core, with its own independent signature re-verification
  (does not import this repo's `app/` package — see
  `tests/boundary/test_no_core_imports.py`).

## What's explicitly NOT verified (see ASSUMPTIONS.md for full detail)

- **Core's real `consent_records` schema.** No P4 repository or
  `complivibe-backend-v5-readonly` clone exists in this build
  environment. `core-side-patch/migrations/0001_...py` defends against
  this by inspecting the live schema at migration time rather than
  assuming a column is absent, but the assumed candidate column names
  have not been checked against real core source.
- **Core's real vendor-risk-finding creation mechanism.** The stub in
  `core-side-patch/routes/patent_ingest_p6.py` calls a placeholder
  (`_create_vendor_risk_finding_via_existing_module`) that raises
  `NotImplementedError` — wire this to the real function once core
  source is available. Do not invent a parallel vendor-risk table.
- **Core's org public-key lookup.** `_lookup_org_public_key()` is a
  stub for the same reason.
- **The wire contract itself** (`/export/consent_records`,
  `/export/registered_processors`, `/internal/consent-propagation/records`,
  `/internal/vendor-risk/findings`) is this build's best guess at a
  contract consistent with the rest of the system, not a verified API.

## Before this goes anywhere near production

1. Get the real core repo/clone and re-run Phase 6 (schema/contract
   verification) for real.
2. Replace the three `NotImplementedError` stubs in
   `core-side-patch/routes/patent_ingest_p6.py`.
3. Have qualified patent counsel review `PATENT.md`'s prior-art and
   approval-likelihood claims before any provisional filing — those
   claims were supplied, not independently researched, in this build.
4. Load-test the retry/escalation scheduler under real webhook latency
   before trusting the 30s/2min/5min timings in production.

## Test suite

30 tests, 96% statement coverage (`coverage run -m pytest tests/ && coverage report -m`).
Boundary audit: `./scripts/boundary_audit.sh` (exit 0 = clean).
