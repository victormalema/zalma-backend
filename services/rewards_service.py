import secrets
import string
from database.supabase_client import get_supabase
from models.rewards import public_ledger_entry, public_referral

# ---------------------------------------------------------------
# PLACEHOLDER REDEMPTION RATE -- not finalized yet.
# Update these once the real rewards structure is decided.
# ---------------------------------------------------------------
MIN_REDEMPTION_POINTS = 100   # smallest number of points you can redeem at once
KES_PER_POINT_REDEEMED = 1    # 1 point = 1 KES off, when redeemed


class RewardsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _generate_discount_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"ZALMA-{suffix}"


def get_rewards_summary(user_id: str) -> dict:
    supabase = get_supabase()

    user_result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user_result.data:
        raise RewardsError("User not found", 404)
    user = user_result.data[0]

    ledger_result = (
        supabase.table("rewards_ledger")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    ledger = [public_ledger_entry(e) for e in ledger_result.data]

    referrals_result = (
        supabase.table("referrals")
        .select("*")
        .eq("referrer_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    referred_ids = [r["referred_id"] for r in referrals_result.data]
    referred_users = {}
    if referred_ids:
        users_result = (
            supabase.table("users").select("id, name, email").in_("id", referred_ids).execute()
        )
        referred_users = {u["id"]: u for u in users_result.data}

    referrals = [
        public_referral(r, referred_users.get(r["referred_id"])) for r in referrals_result.data
    ]

    return {
        "points_balance": user["points_balance"],
        "referral_code": user["referral_code"],
        "ledger": ledger,
        "referrals": referrals,
        "referral_count": len(referrals),
    }


def redeem_points(user_id: str, points: int) -> dict:
    if points < MIN_REDEMPTION_POINTS:
        raise RewardsError(f"Minimum redemption is {MIN_REDEMPTION_POINTS} points")

    supabase = get_supabase()
    user_result = supabase.table("users").select("points_balance").eq("id", user_id).execute()
    if not user_result.data:
        raise RewardsError("User not found", 404)

    current_balance = user_result.data[0]["points_balance"]
    if points > current_balance:
        raise RewardsError("You don't have enough points for that", 409)

    new_balance = current_balance - points
    supabase.table("users").update({"points_balance": new_balance}).eq("id", user_id).execute()

    code = _generate_discount_code()
    discount_value = points * KES_PER_POINT_REDEEMED

    supabase.table("rewards_ledger").insert(
        {
            "user_id": user_id,
            "type": "redeem",
            "points": -points,
            "description": f"Redeemed for code {code} (KES {discount_value} off)",
        }
    ).execute()

    return {
        "code": code,
        "discount_value": discount_value,
        "points_redeemed": points,
        "new_balance": new_balance,
    }
