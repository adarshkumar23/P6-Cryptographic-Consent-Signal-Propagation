"""
PATENT.md Component 4 — three-stage non-acknowledgement escalation:
  1. automatic retry with exponential backoff (30s, 2min, 5min)
  2. human escalation to a designated compliance owner once retries
     are exhausted
  3. a vendor-risk flag pushed into core's existing vendor management
     module for prolonged non-acknowledgement

This module does not itself sleep/schedule wall-clock time — it is
driven by an external scheduler (cron/worker) that calls
next_action() with the current time and the attempt history, and this
module decides which of the three stages applies. That keeps the
escalation *policy* unit-testable without real waiting.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ConsentToken,
    EscalationRecord,
    RegisteredProcessor,
    VendorFlagRecord,
)
from app.services.chain_builder import ChainBuilder
from app.services.core_push_client import CorePushClient
from app.services.propagation_dispatcher import PropagationDispatcher


class Stage(str, Enum):
    RETRY = "retry"
    HUMAN = "human"
    VENDOR_FLAG = "vendor_flag"
    DONE = "done"


class EscalationScheduler:
    def __init__(
        self,
        session: Session,
        dispatcher: PropagationDispatcher,
        core_push_client: CorePushClient | None = None,
    ):
        self.session = session
        self.dispatcher = dispatcher
        self.core_push_client = core_push_client
        self.chain = ChainBuilder(session)
        settings = get_settings()
        self.backoff_sequence = settings.retry_backoff_sequence  # [30, 120, 300]
        self.non_ack_escalation_window = timedelta(hours=settings.escalation_non_ack_hours)

    def next_action(
        self, retries_completed: int, first_attempt_at: datetime, now: datetime
    ) -> Stage:
        """Pure decision function: given how many retries have already
        run and when the first attempt happened, what should happen
        next? retries_completed does not include the initial attempt."""
        if retries_completed < len(self.backoff_sequence):
            return Stage.RETRY
        elapsed = now - first_attempt_at
        if elapsed >= self.non_ack_escalation_window:
            return Stage.VENDOR_FLAG
        return Stage.HUMAN

    def backoff_for_retry(self, retry_number: int) -> int:
        """retry_number is 1-indexed: 1 -> 30s, 2 -> 120s, 3 -> 300s."""
        return self.backoff_sequence[retry_number - 1]

    def run_retry(
        self, token: ConsentToken, processor: RegisteredProcessor, retry_number: int
    ):
        attempt = self.dispatcher.redispatch(token, processor, attempt_number=retry_number + 1)
        record = EscalationRecord(
            token_id=token.token_id,
            processor_id=processor.id,
            stage=Stage.RETRY.value,
            retry_attempt_number=retry_number,
            details=f"retry {retry_number} after {self.backoff_for_retry(retry_number)}s backoff",
        )
        self.session.add(record)
        self.session.flush()

        self.chain.append(
            token.processing_activity_id,
            record_type="escalation",
            content={
                "stage": Stage.RETRY.value,
                "retry_number": retry_number,
                "attempt_id": attempt.id,
                "escalation_record_id": record.id,
            },
        )
        return attempt, record

    def escalate_to_human(
        self, token: ConsentToken, processor: RegisteredProcessor, compliance_owner: str
    ) -> EscalationRecord:
        record = EscalationRecord(
            token_id=token.token_id,
            processor_id=processor.id,
            stage=Stage.HUMAN.value,
            details=f"escalated to compliance owner {compliance_owner} after retries exhausted",
        )
        self.session.add(record)
        self.session.flush()

        self.chain.append(
            token.processing_activity_id,
            record_type="escalation",
            content={
                "stage": Stage.HUMAN.value,
                "escalation_record_id": record.id,
                "compliance_owner": compliance_owner,
            },
        )
        return record

    def flag_vendor_risk(
        self, token: ConsentToken, processor: RegisteredProcessor, reason: str
    ) -> VendorFlagRecord:
        flag = VendorFlagRecord(
            org_id=token.org_id,
            processor_id=processor.id,
            token_id=token.token_id,
            reason=reason,
        )
        self.session.add(flag)
        self.session.flush()

        if self.core_push_client is not None:
            result = self.core_push_client.push_vendor_risk_finding(
                {
                    "vendor_id": processor.id,
                    "finding_type": "consent_propagation_non_acknowledgement",
                    "severity": "high",
                    "description": reason,
                    "source_system": "p6-consent-propagation",
                }
            )
            flag.pushed_to_core = True
            flag.core_finding_id = result.get("id")
            self.session.flush()

        self.chain.append(
            token.processing_activity_id,
            record_type="vendor_flag",
            content={
                "vendor_flag_id": flag.id,
                "processor_id": processor.id,
                "reason": reason,
                "pushed_to_core": flag.pushed_to_core,
            },
        )
        return flag
