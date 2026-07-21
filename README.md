# P6 — Cryptographic Consent Signal Propagation

A satellite service that gives an organization a cryptographically
verifiable answer to "did every downstream processor actually receive
and process this consent withdrawal, and can you prove it to a
regulator" — see `PATENT.md` for the full technical disclosure this
repository implements.

## What this is

1. **Signed consent tokens** — a consent grant/withdrawal is turned
   into an Ed25519-signed token containing only a SHA-256 hash of the
   data subject's identifier, never the raw value.
2. **Signed processor acknowledgement receipts** — each downstream
   processor must sign its own acknowledgement with its own key. An
   HTTP 200 alone is never treated as proof of receipt.
3. **Hash-chained propagation records** — every dispatch, ack, retry,
   escalation, and vendor-risk flag is linked into an append-only hash
   chain that can be independently verified for tampering.
4. **Three-stage escalation** — automatic retry (30s/2min/5min) → human
   escalation to the compliance owner → vendor-risk flag in core's
   vendor management module for prolonged non-acknowledgement.

## Repository layout

```
app/
  crypto/            Ed25519 signing, per-org encrypted key storage
  services/          token emission, dispatch, chain, escalation, core clients
  api/                webhook callback route for async acknowledgements
core-side-patch/      NOT part of this app — a patch intended for CompliVibe core
tests/
  unit/               crypto + token emission, in isolation
  integration/        dispatch/ack/chain/escalation end-to-end
  boundary/           structural guarantees (no raw identifiers, no core imports)
```

## Running locally

```bash
cp .env.example .env
# fill in SATELLITE_KEK: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Running tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
./scripts/boundary_audit.sh
```

## Important: read ASSUMPTIONS.md before relying on this against real core

This satellite is designed to EXTEND core's existing `consent_records`
table, not build a parallel consent system. No real core repository or
read-only clone was available while building this, so `core_read_client.py`,
`core_push_client.py`, and everything in `core-side-patch/` are written
against an **assumed** contract. `ASSUMPTIONS.md` lists every place this
needs to be re-verified against real core source before it's trusted in
production.

Likewise, the "no identified prior art" claim in `PATENT.md` reflects
the project's internal positioning, not an independently performed
patent search — see `PATENT.md`'s own note on this before filing.
