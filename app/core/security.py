"""import hashlib
import secrets

import jwt 
from app.core.config import cfg 


def generate_salt():
    return secrets.token_hex(16)


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)"""


    