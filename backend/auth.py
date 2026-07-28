"""
Auth utilities: password hashing, JWT issuing/verification, and Google ID
token verification.

Environment variables needed:
  JWT_SECRET_KEY   - required in production; a long random string.
                     Falls back to a dev-only default locally so you're not
                     blocked before deploying, but this MUST be overridden
                     via Railway's environment variables in production.
  GOOGLE_CLIENT_ID - the OAuth Client ID from Google Cloud Console, used to
                     verify that a Google sign-in token was actually issued
                     for THIS app (not some other app impersonating you).
"""

import os
import datetime
import secrets
import bcrypt
import jwt
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

_DEV_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEV_DEFAULT_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # tokens last a week; re-login after that

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

# Refuse to start in production with an insecure/default secret - this is the
# single most important thing standing between "tokens are real" and "anyone
# can forge a valid login token for any user." Set JWT_SECRET_KEY to a long
# random value (e.g. `openssl rand -hex 32`) as a Railway environment variable.
if ENVIRONMENT == "production" and JWT_SECRET_KEY == _DEV_DEFAULT_SECRET:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set (or still the insecure default) while "
        "ENVIRONMENT=production. Set a real random JWT_SECRET_KEY before "
        "deploying - refusing to start with a forgeable secret."
    )


def hash_password(password: str) -> str:
    # bcrypt has a hard 72-byte input limit - truncate defensively so an
    # unusually long password doesn't raise instead of just being hashed.
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) if the token is invalid/expired."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def verify_google_id_token(token: str) -> dict:
    """
    Verifies a Google ID token (from the frontend's Google Sign-In button)
    against Google's public keys and checks it was issued for THIS app's
    client ID. Returns the decoded token payload (contains email, name, sub).
    Raises ValueError if invalid.
    """
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID is not configured on the backend")

    idinfo = google_id_token.verify_oauth2_token(
        token, google_requests.Request(), GOOGLE_CLIENT_ID
    )
    return idinfo


def generate_secure_token() -> str:
    """Used for email verification links and password reset links - stored
    in the DB (not a JWT), so it can be invalidated by clearing the column
    once used, unlike a stateless JWT which stays valid until it expires."""
    return secrets.token_urlsafe(32)
