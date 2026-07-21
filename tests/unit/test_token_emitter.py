from app.crypto.keys import generate_org_keypair
from app.crypto.signing import verify_signature
from app.models import OrgSigningKey
from app.services.token_emitter import ConsentTokenEmitter


def _make_org(session, org_id="org-1"):
    material = generate_org_keypair(org_id)
    key = OrgSigningKey(
        org_id=org_id,
        public_key=material.public_key_bytes,
        encrypted_private_key=material.encrypted_private_key,
        subject_hash_salt=material.subject_hash_salt,
    )
    session.add(key)
    session.flush()
    return key, material


def test_emit_produces_a_validly_signed_token(db_session):
    key, material = _make_org(db_session)
    token = ConsentTokenEmitter(db_session).emit(
        data_subject_id="subject-a",
        processing_activity_id="activity-1",
        decision="withdraw",
        org_id="org-1",
    )
    import json

    payload = json.loads(token.canonical_payload)
    assert verify_signature(material.public_key, payload, token.signature) is True


def test_hash_differs_per_org_salt_for_same_subject(db_session):
    key1, _ = _make_org(db_session, "org-1")
    key2, _ = _make_org(db_session, "org-2")

    emitter = ConsentTokenEmitter(db_session)
    t1 = emitter.emit(
        data_subject_id="same-subject",
        processing_activity_id="activity-1",
        decision="withdraw",
        org_id="org-1",
    )
    t2 = emitter.emit(
        data_subject_id="same-subject",
        processing_activity_id="activity-1",
        decision="withdraw",
        org_id="org-2",
    )
    assert t1.hashed_subject != t2.hashed_subject


def test_same_org_same_subject_hashes_consistently(db_session):
    _make_org(db_session, "org-1")
    emitter = ConsentTokenEmitter(db_session)
    t1 = emitter.emit(
        data_subject_id="same-subject",
        processing_activity_id="activity-1",
        decision="withdraw",
        org_id="org-1",
    )
    t2 = emitter.emit(
        data_subject_id="same-subject",
        processing_activity_id="activity-2",
        decision="grant",
        org_id="org-1",
    )
    assert t1.hashed_subject == t2.hashed_subject


def test_invalid_decision_rejected(db_session):
    _make_org(db_session)
    emitter = ConsentTokenEmitter(db_session)
    try:
        emitter.emit(
            data_subject_id="x",
            processing_activity_id="a",
            decision="maybe",
            org_id="org-1",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
