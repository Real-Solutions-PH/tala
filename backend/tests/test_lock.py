from kapiling.auth.lock import hash_pin, verify_pin


def test_hash_and_verify():
    h = hash_pin("1234")
    assert h.startswith("scrypt$") and h.count("$") == 2
    assert verify_pin("1234", h) and not verify_pin("1235", h)
    assert hash_pin("1234") != h
    assert not verify_pin("1234", "garbage")
