"""
Receives asynchronous processor acknowledgement callbacks. Verifies
the processor's signature BEFORE accepting anything as a valid
acknowledgement — an unsigned or invalidly-signed "ack" is rejected
and never reaches the hash chain.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AcknowledgementReceipt, PropagationAttempt
from app.services.chain_builder import ChainBuilder
from app.services.receipt_verifier import ReceiptVerifier

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class AcknowledgementCallback(BaseModel):
    attempt_id: str
    processor_id: str
    payload: dict
    signature_hex: str


@router.post("/processor-acknowledgement")
def receive_acknowledgement(
    body: AcknowledgementCallback, session: Session = Depends(get_session)
):
    result = accept_acknowledgement(
        session,
        attempt_id=body.attempt_id,
        processor_id=body.processor_id,
        payload=body.payload,
        signature=bytes.fromhex(body.signature_hex),
    )
    if not result["accepted"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


def accept_acknowledgement(
    session: Session,
    *,
    attempt_id: str,
    processor_id: str,
    payload: dict,
    signature: bytes,
) -> dict:
    attempt = session.get(PropagationAttempt, attempt_id)
    if attempt is None:
        return {"accepted": False, "reason": "unknown attempt_id"}

    verifier = ReceiptVerifier(session)
    valid = verifier.verify(processor_id, payload, signature)

    receipt = AcknowledgementReceipt(
        attempt_id=attempt_id,
        token_id=attempt.token_id,
        processor_id=processor_id,
        canonical_payload=__import__("json").dumps(payload, sort_keys=True, separators=(",", ":")),
        signature=signature,
        signature_valid=valid,
    )
    session.add(receipt)
    session.flush()

    if not valid:
        # Not chained: an invalidly-signed ack is not evidence of anything.
        return {"accepted": False, "reason": "invalid signature", "receipt_id": receipt.id}

    from app.models import ConsentToken

    token = session.get(ConsentToken, attempt.token_id)
    ChainBuilder(session).append(
        token.processing_activity_id,
        record_type="ack",
        content={
            "receipt_id": receipt.id,
            "attempt_id": attempt_id,
            "token_id": attempt.token_id,
            "processor_id": processor_id,
        },
    )
    return {"accepted": True, "receipt_id": receipt.id}
