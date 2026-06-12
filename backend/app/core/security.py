import hashlib
import hmac
import secrets
import string


def generate_client_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def verify_token(token: str, token_hash: str, secret: str) -> bool:
    return hmac.compare_digest(hash_token(token, secret), token_hash)


def generate_room_code(length: int = 5) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
