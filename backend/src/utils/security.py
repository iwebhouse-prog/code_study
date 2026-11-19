import hashlib

import bcrypt

BCRYPT_ROUNDS = 12  # research.md section 8, data-model.md users.password_hash
BCRYPT_MAX_PASSWORD_BYTES = 72  # bcrypt ignores everything after 72 bytes


class PasswordTooLongError(ValueError):
    pass


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes in UTF-8"
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Returns False for a wrong password; raises ValueError for a broken hash."""
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        # hash_password never stores such a password, so it cannot match.
        return False
    return bcrypt.checkpw(encoded, password_hash.encode())


def hash_token(token: str) -> str:
    """SHA-256 hex digest; refresh tokens are stored only in this form.

    A fast hash is safe here because tokens are long and random, unlike passwords.
    """
    return hashlib.sha256(token.encode()).hexdigest()
