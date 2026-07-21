"""
PATENT.md Component 3 — hash-chained propagation record.

record_hash = sha256(previous_hash + canonical(record_content))

Chains are scoped per processing_activity_id. The genesis record's
previous_hash is a fixed, documented sentinel ("0" * 64) so an empty
chain has a well-defined starting point.
"""
import hashlib

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crypto.signing import canonicalize
from app.models import PropagationRecord

GENESIS_HASH = "0" * 64


class ChainTamperedError(Exception):
    def __init__(self, activity_id: str, sequence_number: int):
        self.activity_id = activity_id
        self.sequence_number = sequence_number
        super().__init__(
            f"propagation chain for {activity_id!r} broken at sequence "
            f"{sequence_number}"
        )


class ChainBuilder:
    def __init__(self, session: Session):
        self.session = session

    def _latest(self, processing_activity_id: str) -> PropagationRecord | None:
        return (
            self.session.query(PropagationRecord)
            .filter_by(processing_activity_id=processing_activity_id)
            .order_by(PropagationRecord.sequence_number.desc())
            .first()
        )

    def append(
        self, processing_activity_id: str, record_type: str, content: dict
    ) -> PropagationRecord:
        latest = self._latest(processing_activity_id)
        previous_hash = latest.record_hash if latest else GENESIS_HASH
        sequence_number = (latest.sequence_number + 1) if latest else 1

        content_bytes = canonicalize(content)
        record_hash = hashlib.sha256(previous_hash.encode("utf-8") + content_bytes).hexdigest()

        record = PropagationRecord(
            processing_activity_id=processing_activity_id,
            sequence_number=sequence_number,
            record_type=record_type,
            record_content=content_bytes.decode("utf-8"),
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def verify_full_chain(self, processing_activity_id: str) -> tuple[bool, int | None]:
        """Walks every record in sequence order. Returns (True, None) if
        the chain is intact, or (False, sequence_number) of the first
        broken link."""
        records = (
            self.session.query(PropagationRecord)
            .filter_by(processing_activity_id=processing_activity_id)
            .order_by(PropagationRecord.sequence_number.asc())
            .all()
        )

        previous_hash = GENESIS_HASH
        for record in records:
            if record.previous_hash != previous_hash:
                return False, record.sequence_number

            expected_hash = hashlib.sha256(
                previous_hash.encode("utf-8") + record.record_content.encode("utf-8")
            ).hexdigest()
            if expected_hash != record.record_hash:
                return False, record.sequence_number

            previous_hash = record.record_hash

        return True, None
