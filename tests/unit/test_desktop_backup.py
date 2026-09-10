import hashlib

from triada_desktop.bundle_security import decrypt_payload, encrypt_payload


def test_encrypted_bundle_roundtrip_and_wrong_password():
    payload = b'{"cookies":[{"name":"session"}]}'
    blob = encrypt_payload(payload, "correct horse battery staple", kind="account-metadata")
    assert decrypt_payload(blob, "correct horse battery staple", expected_kind="account-metadata") == payload
    try:
        decrypt_payload(blob, "wrong password", expected_kind="account-metadata")
    except ValueError:
        pass
    else:
        raise AssertionError("wrong password must fail")


def test_bundle_contains_unique_nonce_and_salt():
    payload = b"same"
    a = encrypt_payload(payload, "password123", kind="test")
    b = encrypt_payload(payload, "password123", kind="test")
    assert a != b


def test_sha256_is_stable():
    data = b"triada"
    assert hashlib.sha256(data).hexdigest() == "cc0960ce566f6fb45b20db94ea2bdda6d35c8983eba7da54f1fe0e23194df195"
