"""
FastAPI dependency for protecting routes: extracts the Bearer token from the
Authorization header, validates it, and loads the corresponding user from
the database. Raises 401 if anything's wrong.

Also provides a WebSocket variant, since the simulation WebSocket can't send
custom headers during the handshake in a browser - it authenticates via a
`token` query parameter instead (e.g. ws://.../ws/simulate?token=...).
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from db import get_db
from models import User
from auth import decode_access_token
from email_utils import EMAIL_ENABLED

bearer_scheme = HTTPBearer()


def _load_user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Only enforce verification if an email provider is actually configured -
    # otherwise nobody could ever verify their email, which would lock
    # everyone out of a deployment that just hasn't set up SMTP yet.
    if EMAIL_ENABLED and not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="EMAIL_NOT_VERIFIED")

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _load_user_from_token(credentials.credentials, db)


def get_current_user_ws(token: str, db: Session) -> User:
    """Same as get_current_user, but for WebSocket handlers where the token
    arrives as a query parameter instead of a header (see main.py)."""
    return _load_user_from_token(token, db)
