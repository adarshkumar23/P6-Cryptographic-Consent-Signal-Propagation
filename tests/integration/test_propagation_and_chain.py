import json

import httpx
import pytest

from app.api.routes_webhooks import accept_acknowledgement
from app.crypto.keys import generate_org_keypair, generate_processor_keypair
from app.crypto.signing import sign_payload
from app.models import OrgSigningKey, RegisteredProcessor
from app.services.chain_builder import ChainBuilder
from app.services.propagation_dispatcher import PropagationDispatcher
from app.services.token_emitter import ConsentTokenEmitter


def _setup_org_and_token(session, org_id="org-1", activity="activity-1"):
    material = generate_org_keypair(org_id)
    session.add(
        OrgSigningKey(
            org_id=org_id,
            public_key=material.public_key_bytes,
            encrypted_private_key=material.encrypted_private_key,
            subject_hash_salt=material.subject_hash_salt,
        )
    )
    session.flush()
    token = ConsentTokenEmitter(session).emit(
        data_subject_id="subject-x",
        processing_activity_id=activity,
        decision="withdraw",
        org_id=org_id,
    )
    session.commit()
    return token


def _register_processor(session, activity, url, status_code=200):
    priv, pub_bytes = generate_processor_keypair()
    processor = RegisteredProcessor(
        org_id="org-1",
        processing_activity_id=activity,
        processor_name=url,
        webhook_url=url,
        public_key=pub_bytes,
    )
    session.add(processor)
    session.flush()
    return processor, priv


def _mock_transport(status_code=200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"ok": status_code < 400})

    return httpx.MockTransport(handler)


def test_propagation_dispatches_to_all_registered_processors(db_session):
    token = _setup_org_and_token(db_session)
    p1, _ = _register_processor(db_session, "activity-1", "https://proc-a.example/hook")
    p2, _ = _register_processor(db_session, "activity-1", "https://proc-b.example/hook")

    client = httpx.Client(transport=_mock_transport(200))
    dispatcher = PropagationDispatcher(db_session, http_client=client)
    attempts = dispatcher.propagate(token)

    assert len(attempts) == 2
    assert {a.processor_id for a in attempts} == {p1.id, p2.id}
    assert all(a.status == "success" for a in attempts)


def test_dispatch_recorded_even_on_processor_failure(db_session):
    token = _setup_org_and_token(db_session)
    _register_processor(db_session, "activity-1", "https://proc-down.example/hook")

    client = httpx.Client(transport=_mock_transport(500))
    dispatcher = PropagationDispatcher(db_session, http_client=client)
    attempts = dispatcher.propagate(token)

    assert len(attempts) == 1
    assert attempts[0].status == "failure"
    assert attempts[0].response_summary  # evidence recorded regardless of outcome


def test_acknowledgement_rejected_without_valid_signature(db_session):
    token = _setup_org_and_token(db_session)
    processor, proc_priv = _register_processor(db_session, "activity-1", "https://p.example/hook")

    client = httpx.Client(transport=_mock_transport(200))
    dispatcher = PropagationDispatcher(db_session, http_client=client)
    attempt = dispatcher.propagate(token)[0]

    payload = {"attempt_id": attempt.id, "received": True}
    bogus_signature = b"\x00" * 64

    result = accept_acknowledgement(
        db_session,
        attempt_id=attempt.id,
        processor_id=processor.id,
        payload=payload,
        signature=bogus_signature,
    )
    assert result["accepted"] is False

    chain_ok, _ = ChainBuilder(db_session).verify_full_chain("activity-1")
    assert chain_ok is True  # invalid ack never entered the chain


def test_acknowledgement_accepted_and_chained_when_valid(db_session):
    token = _setup_org_and_token(db_session)
    processor, proc_priv = _register_processor(db_session, "activity-1", "https://p.example/hook")

    client = httpx.Client(transport=_mock_transport(200))
    dispatcher = PropagationDispatcher(db_session, http_client=client)
    attempt = dispatcher.propagate(token)[0]

    payload = {"attempt_id": attempt.id, "received": True}
    signature = sign_payload(proc_priv, payload)

    result = accept_acknowledgement(
        db_session,
        attempt_id=attempt.id,
        processor_id=processor.id,
        payload=payload,
        signature=signature,
    )
    assert result["accepted"] is True

    chain_ok, broken_at = ChainBuilder(db_session).verify_full_chain("activity-1")
    assert chain_ok is True
    assert broken_at is None


def test_chain_verification_passes_on_untampered_chain(db_session):
    chain = ChainBuilder(db_session)
    chain.append("activity-9", "dispatch", {"a": 1})
    chain.append("activity-9", "ack", {"b": 2})
    chain.append("activity-9", "escalation", {"c": 3})
    db_session.commit()

    ok, broken_at = chain.verify_full_chain("activity-9")
    assert ok is True
    assert broken_at is None


def test_chain_verification_detects_any_tampering(db_session):
    chain = ChainBuilder(db_session)
    chain.append("activity-9", "dispatch", {"a": 1})
    r2 = chain.append("activity-9", "ack", {"b": 2})
    chain.append("activity-9", "escalation", {"c": 3})
    db_session.commit()

    # Tamper with the middle record's content directly in storage.
    r2.record_content = json.dumps({"b": "tampered"})
    db_session.commit()

    ok, broken_at = chain.verify_full_chain("activity-9")
    assert ok is False
    assert broken_at == r2.sequence_number
