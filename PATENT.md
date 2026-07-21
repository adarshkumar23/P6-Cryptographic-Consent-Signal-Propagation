# Patent Technical Specification
## CompliVibe Cryptographic Consent Signal Propagation System

**Repository:** complivibe-patent-p6-consent-propagation
**First committed:** 2026-07-21
**Status:** Pre-filing technical specification
**Priority assessment:** Lowest approval difficulty in the P5-P10
portfolio — file this patent first.

## Technical Problem Being Solved
When a data subject withdraws consent under GDPR Article 7(3), an
organization must notify every downstream processor and cease
processing. In practice, organizations send notifications (typically
email) and have no technical mechanism to prove those notifications
were received or acted upon. When a regulator asks whether all
processors were notified within the required timeframe, the honest
answer is usually "we sent emails and hope they arrived" — this is
not verifiable compliance, it is wishful record-keeping. An HTTP 200
response from a webhook proves a request was received by *something*,
not that the receiving system genuinely processed and acted on the
consent decision.

## The Novel Technical Method
Component 1 — Signed Consent Token Emission: on a consent grant or
withdrawal event, a token is constructed containing a SHA-256 hash of
the data subject's identifier (never the raw identifier), the
processing activity ID, the decision, a timestamp, and a unique token
ID, signed with the organization's Ed25519 private key. The raw data
subject identifier never appears in the token, in any propagation
record, or in the audit chain — only its one-way hash does. This
means the propagation system itself processes no personal data, only
cryptographic derivatives of it.

Component 2 — Signed Processor Acknowledgement Receipts: each
downstream processor registered for the affected processing activity
receives the signed token via webhook and must return a receipt
independently signed with the processor's own registered private key,
covering the specific token content. A valid signature proves genuine
receipt and processing in a way an HTTP 200 status code cannot — a
misconfigured or non-compliant system can return 200 without having
processed anything; it cannot produce a valid signature over content
it never actually received and validated.

Component 3 — Hash-Chained Propagation Record: every propagation
record (dispatch attempt, acknowledgement, timestamp) is linked into
an append-only hash chain, where each record includes the hash of the
immediately preceding record. Tampering with any record invalidates
verification of every subsequent record, making the complete
propagation history provably tamper-evident. A regulator can verify
the chain cryptographically without trusting any party's self-reported
claim of compliance.

Component 4 — Three-Stage Non-Acknowledgement Escalation: automatic
retry with exponential backoff (30s, 2min, 5min), followed by human
escalation to a designated compliance owner after retries are
exhausted, followed by a vendor-risk flag in the existing vendor
management module for prolonged non-acknowledgement — connecting
consent propagation failure to the organization's broader vendor risk
posture rather than treating it as an isolated notification failure.

## What Distinguishes This From Prior Art
Consent Management Platforms (OneTrust, Cookiebot, TrustArc) record
consent decisions and log notification attempts. None cryptographically
sign consent tokens, none require a signed acknowledgement receipt
from downstream processors (as distinct from a bare HTTP status), and
none construct a hash-chained, independently verifiable audit record
of the complete propagation. This three-component combination —
signed emission, signed acknowledgement, hash-chained record — has no
identified prior art.

## Filing Intent
Provisional patent filing within 90 days of this commit. This is the
highest-priority filing in the P5-P10 portfolio given its assessed
approval likelihood.

## Note on Novelty and Prior-Art Claims

The "no identified prior art" and priority/approval-likelihood
statements above reflect this project's internal positioning as
supplied at authoring time. They are not the product of a formal
prior-art search or legal opinion, and should not be treated as one.
Before any actual filing, these claims require independent
verification by qualified patent counsel, including a real search
against issued patents and published applications in the consent-
management, PKI/signed-webhook, and audit-log-chaining spaces.
