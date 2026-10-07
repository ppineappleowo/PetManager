import hashlib
import secrets

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000)
    return f'{salt}:{key.hex()}'

def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split(':', 1)
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000)
        return secrets.compare_digest(key.hex(), expected)
    except (ValueError, AttributeError):
        return False
