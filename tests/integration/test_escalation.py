from datetime import datetime, timedelta, timezone

import httpx

from app.crypto.keys import generate_org_keypair, generate_processor_keypair
from app.models import OrgSigningKey, RegisteredProcessor
from app.services.chain_builder import ChainBuilder
from app.services.core_push_client import CorePushClient
from app.services.escalation_scheduler import EscalationScheduler, Stage
from app.services.propagation_dispatcher import PropagationDispatcher
from app.services.token_emitter import ConsentTokenEmitter


def _setup(session):
    material = generate_org_keypair("org-1")
    session.add(
        OrgSigningKey(
            org_id="org-1",
            public_key=material.public_key_bytes,
            encrypted_private_key=material.encrypted_private_key,
            subject_hash_salt=material.subject_hash_salt,
        )
    )
    session.flush()
    token = ConsentTokenEmitter(session).emit(
        data_subject_id="subject-x",
        processing_activity_id="activity-1",
        decision="withdraw",
        org_id="org-1",
    )
    priv, pub = generate_processor_keypair()
    processor = RegisteredProcessor(
        org_id="org-1",
        processing_activity_id="activity-1",
        processor_name="slow-processor",
        webhook_url="https://slow.example/hook",
        public_key=pub,
    )
    session.add(processor)
    session.flush()
    session.commit()
    return token, processor


def _failing_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_retry_backoff_follows_30s_2min_5min_sequence(db_session):
    dispatcher = PropagationDispatcher(db_session, http_client=_failing_client())
    scheduler = EscalationScheduler(db_session, dispatcher)
    assert [scheduler.backoff_for_retry(i) for i in (1, 2, 3)] == [30, 120, 300]


def test_next_action_returns_retry_while_retries_remain(db_session):
    dispatcher = PropagationDispatcher(db_session, http_client=_failing_client())
    scheduler = EscalationScheduler(db_session, dispatcher)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert scheduler.next_action(0, now, now) == Stage.RETRY
    assert scheduler.next_action(2, now, now) == Stage.RETRY


def test_escalation_created_after_retries_exhausted(db_session):
    token, processor = _setup(db_session)
    dispatcher = PropagationDispatcher(db_session, http_client=_failing_client())
    scheduler = EscalationScheduler(db_session, dispatcher)

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_attempt_at = now
    stage = scheduler.next_action(3, first_attempt_at, now + timedelta(minutes=10))
    assert stage == Stage.HUMAN

    record = scheduler.escalate_to_human(token, processor, compliance_owner="dpo@example.com")
    assert record.stage == Stage.HUMAN.value

    chain_ok, _ = ChainBuilder(db_session).verify_full_chain("activity-1")
    assert chain_ok is True


def test_vendor_flag_created_after_prolonged_non_acknowledgement(db_session):
    token, processor = _setup(db_session)
    dispatcher = PropagationDispatcher(db_session, http_client=_failing_client())

    def core_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "core-finding-123"})

    core_client = CorePushClient(http_client=httpx.Client(base_url="https://core.internal.example", transport=httpx.MockTransport(core_handler)))
    scheduler = EscalationScheduler(db_session, dispatcher, core_push_client=core_client)

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stage = scheduler.next_action(3, now, now + timedelta(hours=49))
    assert stage == Stage.VENDOR_FLAG

    flag = scheduler.flag_vendor_risk(token, processor, reason="no acknowledgement after 49 hours")
    assert flag.pushed_to_core is True
    assert flag.core_finding_id == "core-finding-123"


def test_push_to_core_creates_propagation_record(db_session):
    token, processor = _setup(db_session)
    dispatcher = PropagationDispatcher(db_session, http_client=_failing_client())

    calls = []

    def core_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(201, json={"id": "core-finding-999"})

    core_client = CorePushClient(http_client=httpx.Client(base_url="https://core.internal.example", transport=httpx.MockTransport(core_handler)))
    scheduler = EscalationScheduler(db_session, dispatcher, core_push_client=core_client)

    flag = scheduler.flag_vendor_risk(token, processor, reason="test push")

    assert len(calls) == 1
    assert flag.pushed_to_core is True

    records = ChainBuilder(db_session).verify_full_chain("activity-1")
    assert records[0] is True
