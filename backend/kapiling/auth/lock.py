import hashlib
import hmac
import os

_N, _R, _P = 2**14, 8, 1


def _scrypt(pin: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pin.encode(), salt=salt, n=_N, r=_R, p=_P)


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    return f"scrypt${salt.hex()}${_scrypt(pin, salt).hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        return hmac.compare_digest(_scrypt(pin, bytes.fromhex(salt_hex)), bytes.fromhex(hash_hex))
    except ValueError:
        return False
