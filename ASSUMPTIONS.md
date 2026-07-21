# ASSUMPTIONS.md

Living merge gate. Updated as findings occur during the build, not
bolted on at the end. Every entry states what was assumed, why, and
what would need to happen before merge/filing to retire the
assumption.

---

## 2026-07-21 — No prior P4 repository or core read-only clone present

**Finding:** The build prompt for this repository references "standing
rules carried forward from P4" and instructs checking
`~/complivibe-backend-v5-readonly` for core's real schema (specifically
whether `consent_records` already has a `propagation_status` field,
and the real vendor-risk-finding creation mechanism), recloning it if
absent.

**Checked:** Searched the entire filesystem (`find / -iname
"*complivibe*"`, `-iname "*consent*"`, `-iname "*p4*"`) and the home
directory. No such repository, clone, or prior P4 project exists
anywhere on this machine. No URL or credentials for such a clone were
supplied.

**Assumption made:** Since the real core codebase is unavailable, this
build does NOT verify `consent_records`' actual schema or core's real
vendor-risk-finding mechanism against source. Instead:
- `app/services/core_read_client.py` is implemented against an
  **assumed** interface (a read-only export endpoint returning
  `consent_records` and `registered_processors` as JSON), documented
  inline as assumed-not-verified.
- `core-side-patch/migrations/0001_consent_propagation_records.py`
  is written as a **dual-path** migration: it inspects the target
  table for an existing `propagation_status`-equivalent column at
  migration time and only adds one if absent — satisfying "extend,
  don't duplicate" as a runtime check rather than a hardcoded
  assumption, but the correctness of that check against the *real*
  production schema is unverified.
- The vendor-risk push (`escalation_scheduler.py` stage 3) targets an
  assumed `VendorRiskFinding`-shaped payload
  (`vendor_id`, `finding_type`, `severity`, `description`,
  `source_system`) posted to an assumed `POST /internal/vendor-risk/findings`
  endpoint on core. This is a guess at a REST shape consistent with
  how the rest of this satellite talks to core, not a verified
  contract.

**Before merge to a real core integration:** re-run this build's
Phase 6 checks against the actual core repository/clone once
available. Do not treat `core_read_client.py` or the migration's
column-detection logic as validated against production until then.

---

## 2026-07-21 — Patent novelty and prior-art claims are unverified

**Finding:** PATENT.md, as supplied in the build prompt, asserts "no
identified prior art" for the three-component combination, "lowest
approval difficulty," and "file this patent first" priority.

**Assumption made:** These statements were transcribed into PATENT.md
as given — they represent the project's internal positioning, not an
independently performed prior-art search or legal opinion by this
build process. A "Note on Novelty and Prior-Art Claims" section was
added to PATENT.md making this explicit.

**Before filing:** qualified patent counsel must perform an actual
prior-art search (consent management platforms' patent filings,
signed-webhook/PKI acknowledgement patterns, hash-chained audit log
patents) before any provisional filing relies on the "no identified
prior art" claim.

---

## 2026-07-21 — Satellite-local encryption key for OrgSigningKey at rest

**Assumption made:** Per the build prompt's explicit instruction,
private keys in `OrgSigningKey` are encrypted at rest using a
satellite-local secret (`SATELLITE_KEK` env var, Fernet), architecturally
separate from any core production secret/key-storage pattern. Core's
actual key-storage pattern was not available to verify (see clone
finding above) — this is a structural choice mandated by the prompt's
privacy architecture, not a match to a verified core convention.

**Before merge:** confirm core does not already have an organization-
key-encryption convention this should instead reuse or align with,
once core source is available.
