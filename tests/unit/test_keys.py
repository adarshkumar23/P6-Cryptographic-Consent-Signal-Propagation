from app.crypto.keys import generate_org_keypair, load_private_key, load_public_key
from app.crypto.signing import sign_payload, verify_signature


def test_generate_org_keypair_roundtrips_through_encryption():
    material = generate_org_keypair("org-1")
    loaded_priv = load_private_key(material.encrypted_private_key)
    loaded_pub = load_public_key(material.public_key_bytes)

    payload = {"hello": "world"}
    sig = sign_payload(loaded_priv, payload)
    assert verify_signature(loaded_pub, payload, sig) is True


def test_each_org_gets_a_distinct_salt():
    m1 = generate_org_keypair("org-1")
    m2 = generate_org_keypair("org-2")
    assert m1.subject_hash_salt != m2.subject_hash_salt


def test_private_key_is_encrypted_at_rest_not_raw():
    material = generate_org_keypair("org-1")
    from cryptography.hazmat.primitives import serialization

    raw_private_bytes = material.private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    assert raw_private_bytes not in material.encrypted_private_key
    assert material.encrypted_private_key != raw_private_bytes
