"""
Core-side ingest endpoints for records pushed by the P6 satellite.

Self-contained: does NOT import anything from this repo's `app/`
package. If this file is dropped into core, core's only new dependency
is `cryptography` itself (already a near-universal transitive
dependency), not this satellite's code. See
scripts/boundary_audit.sh and ../README.md.

Per the standing rule "satellite computes and signs; it never decides
what core does with a verified result" — core independently
re-verifies the record's signature against the org's public key
(already known to core from org onboarding) before writing or acting
on anything. A record whose signature does not verify here is
rejected, regardless of what the satellite claimed.
"""
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/internal", tags=["p6-ingest"])


def _canonicalize(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _independently_verify(org_public_key_bytes: bytes, payload: dict, signature: bytes) -> bool:
    public_key = Ed25519PublicKey.from_public_bytes(org_public_key_bytes)
    try:
        public_key.verify(signature, _canonicalize(payload))
        return True
    except InvalidSignature:
        return False


class PropagationRecordIngest(BaseModel):
    org_id: str
    payload: dict
    signature_hex: str


class VendorRiskFindingIngest(BaseModel):
    vendor_id: str
    finding_type: str
    severity: str
    description: str
    source_system: str


@router.post("/consent-propagation/records")
def ingest_propagation_record(body: PropagationRecordIngest):
    org_public_key_bytes = _lookup_org_public_key(body.org_id)  # core-owned lookup, not the satellite's
    if not _independently_verify(org_public_key_bytes, body.payload, bytes.fromhex(body.signature_hex)):
        raise HTTPException(status_code=400, detail="signature failed independent re-verification")
    return _persist_propagation_record(body.org_id, body.payload)


@router.post("/vendor-risk/findings")
def ingest_vendor_risk_finding(body: VendorRiskFindingIngest):
    # Connects into core's EXISTING vendor management module — this
    # must call whatever core's real vendor-risk-finding creation
    # mechanism is once verified against source (see ASSUMPTIONS.md).
    # This stub assumes such a mechanism exists and is named
    # create_vendor_risk_finding(); it is NOT invented here as a
    # parallel system.
    return _create_vendor_risk_finding_via_existing_module(body.model_dump())


def _lookup_org_public_key(org_id: str) -> bytes:
    raise NotImplementedError(
        "wire to core's real org public key storage once available — see ASSUMPTIONS.md"
    )


def _persist_propagation_record(org_id: str, payload: dict) -> dict:
    raise NotImplementedError("wire to core's real persistence layer once available")


def _create_vendor_risk_finding_via_existing_module(finding: dict) -> dict:
    raise NotImplementedError(
        "wire to core's EXISTING vendor management module's finding-creation "
        "function once its real signature is verified — see ASSUMPTIONS.md"
    )
