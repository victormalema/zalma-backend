import os

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from database.supabase_client import get_supabase
from models.user import public_user
from services.wraps_service import generate_wrap
from utils.security import (
    hash_password,
    verify_password,
    generate_token,
    generate_referral_code,
)


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")


class AuthError(Exception):
    """Raised for expected auth failures (bad input, duplicate email, wrong password).
    Routes catch this and turn it into a clean JSON error response."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _find_referrer_id(supabase, referral_code: str | None):
    if not referral_code:
        return None
    referrer = (
        supabase.table("users")
        .select("id")
        .eq("referral_code", referral_code.strip().upper())
        .execute()
    )
    # A referral code that doesn't match anyone is ignored rather than
    # blocking signup -- no need to punish a typo.
    return referrer.data[0]["id"] if referrer.data else None


def _record_referral(supabase, referrer_id, referred_id):
    if not referrer_id:
        return
    supabase.table("referrals").insert(
        {
            "referrer_id": referrer_id,
            "referred_id": referred_id,
            "reward_granted": False,
        }
    ).execute()


def signup_user(email: str, password: str, name: str = None,
                 phone: str = None, referral_code: str = None) -> tuple[str, dict]:
    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        raise AuthError("email and password are required")
    if len(password) < 8:
        raise AuthError("password must be at least 8 characters")

    supabase = get_supabase()

    existing = supabase.table("users").select("id").eq("email", email).execute()
    if existing.data:
        raise AuthError("An account with this email already exists", 409)

    referred_by_id = _find_referrer_id(supabase, referral_code)

    new_user = {
        "email": email,
        "password_hash": hash_password(password),
        "name": name,
        "phone": phone,
        "referral_code": generate_referral_code(),
        "referred_by": referred_by_id,
    }

    result = supabase.table("users").insert(new_user).execute()
    user = result.data[0]

    _record_referral(supabase, referred_by_id, user["id"])

    token = generate_token(user["id"])
    generate_wrap(user["id"], "welcome", "Welcome to ZALMA")
    return token, public_user(user)


def login_user(email: str, password: str) -> tuple[str, dict]:
    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        raise AuthError("email and password are required")

    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("email", email).execute()

    if not result.data:
        raise AuthError("Invalid email or password", 401)

    user = result.data[0]
    if not user.get("password_hash"):
        # Account was created via Google and has no password set.
        raise AuthError("This account uses Google sign-in. Please continue with Google.", 401)
    if not verify_password(password, user["password_hash"]):
        raise AuthError("Invalid email or password", 401)

    token = generate_token(user["id"])
    return token, public_user(user)


def google_login_user(credential: str, referral_code: str = None) -> tuple[str, dict]:
    """Sign in or sign up with a Google ID token (the `credential` from Google Identity Services).

    - Existing Google-linked user  -> log in
    - Existing email/password user with same verified email -> link Google, log in
    - Otherwise -> create a new account
    """
    if not credential:
        raise AuthError("Google credential is required")
    if not GOOGLE_CLIENT_ID:
        raise AuthError("Google sign-in is not configured", 500)

    try:
        info = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise AuthError("Invalid Google sign-in. Please try again.", 401)

    if not info.get("email_verified"):
        raise AuthError("Your Google email is not verified", 401)

    google_id = info["sub"]
    email = info["email"].strip().lower()
    name = info.get("name")

    supabase = get_supabase()

    # 1. Already linked to this Google account
    result = supabase.table("users").select("*").eq("google_id", google_id).execute()
    if result.data:
        user = result.data[0]
        return generate_token(user["id"]), public_user(user)

    # 2. Same email already registered -> link accounts (safe: Google verified the email)
    result = supabase.table("users").select("*").eq("email", email).execute()
    if result.data:
        user = result.data[0]
        supabase.table("users").update({"google_id": google_id}).eq("id", user["id"]).execute()
        return generate_token(user["id"]), public_user(user)

    # 3. Brand new user
    referred_by_id = _find_referrer_id(supabase, referral_code)
    new_user = {
        "email": email,
        "password_hash": None,
        "google_id": google_id,
        "name": name,
        "phone": None,
        "referral_code": generate_referral_code(),
        "referred_by": referred_by_id,
    }
    user = supabase.table("users").insert(new_user).execute().data[0]
    _record_referral(supabase, referred_by_id, user["id"])

    generate_wrap(user["id"], "welcome", "Welcome to ZALMA")
    return generate_token(user["id"]), public_user(user)


def get_user_profile(user_id: str) -> dict:
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("id", user_id).execute()

    if not result.data:
        raise AuthError("User not found", 404)

    return public_user(result.data[0])