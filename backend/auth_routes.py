import os
import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from db import get_db
from models import User
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_google_id_token,
    generate_secure_token,
)
from auth_deps import get_current_user
from email_utils import send_verification_email, send_password_reset_email, EMAIL_ENABLED
from rate_limit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
RESET_TOKEN_VALID_HOURS = 1


# ---------- Request/response models ----------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class AuthResponse(BaseModel):
    access_token: str
    email: str
    name: str | None = None
    is_verified: bool = True


class MessageResponse(BaseModel):
    message: str


# ---------- Signup / login ----------

@router.post("/signup", response_model=AuthResponse, dependencies=[Depends(rate_limit(max_attempts=5, window_seconds=300))])
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    verification_token = generate_secure_token() if EMAIL_ENABLED else None

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        name=req.name,
        is_verified=not EMAIL_ENABLED,  # if no email provider configured, don't block real usage
        verification_token=verification_token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if EMAIL_ENABLED:
        send_verification_email(user.email, FRONTEND_URL, verification_token)

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, email=user.email, name=user.name, is_verified=user.is_verified)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(rate_limit(max_attempts=8, window_seconds=300))])
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, email=user.email, name=user.name, is_verified=user.is_verified)


@router.post("/google", response_model=AuthResponse)
def google_login(req: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        idinfo = verify_google_id_token(req.id_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    google_id = idinfo["sub"]
    email = idinfo.get("email")
    name = idinfo.get("name")

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
            user.is_verified = True  # Google already verified this email
        else:
            # Google verifies the email on their end, so we trust it immediately.
            user = User(email=email, google_id=google_id, name=name, is_verified=True)
            db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, email=user.email, name=user.name, is_verified=user.is_verified)


@router.get("/me", response_model=AuthResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return AuthResponse(access_token="", email=current_user.email, name=current_user.name, is_verified=current_user.is_verified)


# ---------- Email verification ----------

@router.post("/verify-email", response_model=MessageResponse)
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == req.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse, dependencies=[Depends(rate_limit(max_attempts=3, window_seconds=600))])
def resend_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_verified:
        return MessageResponse(message="Email is already verified")
    if not EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email sending is not configured on this server")

    current_user.verification_token = generate_secure_token()
    db.commit()
    send_verification_email(current_user.email, FRONTEND_URL, current_user.verification_token)
    return MessageResponse(message="Verification email sent")


# ---------- Password reset ----------

@router.post("/forgot-password", response_model=MessageResponse, dependencies=[Depends(rate_limit(max_attempts=3, window_seconds=600))])
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()

    # Always return the same message whether or not the account exists -
    # confirming/denying an email's existence here would let an attacker
    # enumerate registered accounts.
    generic_message = MessageResponse(message="If an account exists for that email, a reset link has been sent.")

    if not user or not user.hashed_password:
        # No account, or a Google-only account with no password to reset.
        return generic_message

    if not EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email sending is not configured on this server")

    user.reset_token = generate_secure_token()
    user.reset_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=RESET_TOKEN_VALID_HOURS)
    db.commit()

    send_password_reset_email(user.email, FRONTEND_URL, user.reset_token)
    return generic_message


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == req.token).first()

    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.hashed_password = hash_password(req.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return MessageResponse(message="Password reset successfully - you can now sign in")
