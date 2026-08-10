from database.supabase_client import get_supabase
from models.user import public_user
from utils.security import (
    hash_password,
    verify_password,
    generate_token,
    generate_referral_code,
)


class AuthError(Exception):
    """Raised for expected auth failures (bad input, duplicate email, wrong password).
    Routes catch this and turn it into a clean JSON error response."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


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

    referred_by_id = None
    if referral_code:
        referrer = (
            supabase.table("users")
            .select("id")
            .eq("referral_code", referral_code.strip().upper())
            .execute()
        )
        if referrer.data:
            referred_by_id = referrer.data[0]["id"]
        # A referral code that doesn't match anyone is ignored rather than
        # blocking signup -- no need to punish a typo.

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

    if referred_by_id:
        supabase.table("referrals").insert(
            {
                "referrer_id": referred_by_id,
                "referred_id": user["id"],
                "reward_granted": False,
            }
        ).execute()

    token = generate_token(user["id"])
    return token, public_user(user)


def login_user(email: str, password: str) -> tuple[str, dict]:
    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        raise AuthError("email and password are required")

    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("email", email).execute()

    if not result.data or not verify_password(password, result.data[0]["password_hash"]):
        raise AuthError("Invalid email or password", 401)

    user = result.data[0]
    token = generate_token(user["id"])
    return token, public_user(user)


def get_user_profile(user_id: str) -> dict:
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("id", user_id).execute()

    if not result.data:
        raise AuthError("User not found", 404)

    return public_user(result.data[0])
