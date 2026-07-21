"""
PATENT.md Component 2 — verifies a processor's acknowledgement
receipt is signed with THAT processor's own registered public key over
THIS token's exact content. An unsigned or invalidly-signed "ack" is
not an acknowledgement — see routes_webhooks.py, which rejects it
before it ever reaches the hash chain.
"""
import json

from sqlalchemy.orm import Session

from app.crypto.keys import load_public_key
from app.crypto.signing import verify_signature
from app.models import RegisteredProcessor


class ReceiptVerifier:
    def __init__(self, session: Session):
        self.session = session

    def verify(self, processor_id: str, receipt_payload: dict, signature: bytes) -> bool:
        processor = self.session.get(RegisteredProcessor, processor_id)
        if processor is None or not processor.active:
            return False
        public_key = load_public_key(processor.public_key)
        return verify_signature(public_key, receipt_payload, signature)
