import copy

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.crypto.signing import sign_payload, verify_signature


def _keypair():
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def test_valid_signature_verifies():
    priv, pub = _keypair()
    payload = {"token_id": "abc", "decision": "withdraw", "n": 1}
    sig = sign_payload(priv, payload)
    assert verify_signature(pub, payload, sig) is True


def test_signature_verification_fails_on_tampered_payload():
    priv, pub = _keypair()
    payload = {"token_id": "abc", "decision": "withdraw", "n": 1}
    sig = sign_payload(priv, payload)

    tampered = copy.deepcopy(payload)
    tampered["decision"] = "grant"
    assert verify_signature(pub, tampered, sig) is False


def test_signature_fails_on_single_byte_tamper_in_string_field():
    priv, pub = _keypair()
    payload = {"token_id": "abcdefgh"}
    sig = sign_payload(priv, payload)

    tampered = {"token_id": "abcdefgi"}  # last char changed by one
    assert verify_signature(pub, tampered, sig) is False


def test_signature_fails_when_signature_bytes_tampered():
    priv, pub = _keypair()
    payload = {"token_id": "abc"}
    sig = bytearray(sign_payload(priv, payload))
    sig[0] ^= 0xFF
    assert verify_signature(pub, payload, bytes(sig)) is False


def test_signature_fails_with_wrong_public_key():
    priv1, _ = _keypair()
    _, pub2 = _keypair()
    payload = {"token_id": "abc"}
    sig = sign_payload(priv1, payload)
    assert verify_signature(pub2, payload, sig) is False


def test_canonicalization_is_order_independent():
    priv, pub = _keypair()
    payload_a = {"a": 1, "b": 2}
    payload_b = {"b": 2, "a": 1}
    sig = sign_payload(priv, payload_a)
    assert verify_signature(pub, payload_b, sig) is True
