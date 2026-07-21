"""
PATENT.md Component 2 — fans a signed consent token out to every
registered processor for its processing_activity_id. Records a
PropagationAttempt regardless of outcome — the attempt itself is
evidence, and is chained via ChainBuilder either way.

Supports two acknowledgement patterns:
  - synchronous: dispatch_sync() sends the webhook and treats a
    signed receipt returned in the HTTP response body as the ack.
  - asynchronous: dispatch_async_pending() records the attempt as
    "pending" and expects the processor to call back later via
    routes_webhooks.py.
"""
import json

import httpx
from sqlalchemy.orm import Session

from app.models import ConsentToken, PropagationAttempt, RegisteredProcessor
from app.services.chain_builder import ChainBuilder
from app.services.receipt_verifier import ReceiptVerifier


class PropagationDispatcher:
    def __init__(self, session: Session, http_client: httpx.Client | None = None):
        self.session = session
        self.http_client = http_client or httpx.Client(timeout=10.0)
        self.chain = ChainBuilder(session)
        self.receipt_verifier = ReceiptVerifier(session)

    def _registered_processors(self, processing_activity_id: str) -> list[RegisteredProcessor]:
        return (
            self.session.query(RegisteredProcessor)
            .filter_by(processing_activity_id=processing_activity_id, active=True)
            .all()
        )

    def propagate(self, token: ConsentToken) -> list[PropagationAttempt]:
        """Dispatches to every registered processor for this token's
        activity. Returns the list of PropagationAttempt rows, one per
        processor, created regardless of individual success/failure."""
        processors = self._registered_processors(token.processing_activity_id)
        attempts = []
        for processor in processors:
            attempts.append(self._dispatch_one(token, processor, attempt_number=1))
        return attempts

    def _dispatch_one(
        self, token: ConsentToken, processor: RegisteredProcessor, attempt_number: int
    ) -> PropagationAttempt:
        payload = json.loads(token.canonical_payload)
        body = {"payload": payload, "signature": token.signature.hex()}

        status = "failure"
        response_summary = ""
        try:
            response = self.http_client.post(processor.webhook_url, json=body)
            response_summary = f"HTTP {response.status_code}"
            status = "success" if response.status_code < 400 else "failure"
        except httpx.HTTPError as exc:
            response_summary = f"transport error: {exc}"
            status = "failure"

        attempt = PropagationAttempt(
            token_id=token.token_id,
            processor_id=processor.id,
            attempt_number=attempt_number,
            status=status,
            response_summary=response_summary,
        )
        self.session.add(attempt)
        self.session.flush()

        self.chain.append(
            token.processing_activity_id,
            record_type="dispatch",
            content={
                "attempt_id": attempt.id,
                "token_id": token.token_id,
                "processor_id": processor.id,
                "attempt_number": attempt_number,
                "status": status,
                "response_summary": response_summary,
            },
        )
        return attempt

    def redispatch(
        self, token: ConsentToken, processor: RegisteredProcessor, attempt_number: int
    ) -> PropagationAttempt:
        """Used by escalation_scheduler for retry attempts 2 and 3."""
        return self._dispatch_one(token, processor, attempt_number=attempt_number)
