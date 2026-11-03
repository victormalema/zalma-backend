import secrets
import string
from database.supabase_client import get_supabase
from models.rewards import public_ledger_entry, public_referral
from services.referral_service import sweep_signup_bonuses
from services.rewards_config import (
    KES_PER_POINT_REDEEMED,
    MAX_REDEMPTION_PERCENT_OF_ORDER,
    MIN_REDEMPTION_POINTS,
    earn_multiplier,
    next_multiplier_at,
)
# KES_PER_POINT_REDEEMED and MIN_REDEMPTION_POINTS keep their old names, so any code that
# imported them from here keeps working. The values now come from services/rewards_config.py.


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

    # Pay any referral signup rewards not paid yet, before the balance is read.
    # (Must never stop the page from loading.)
    try:
        sweep_signup_bonuses(user_id)
    except Exception:
        pass

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

    lifetime = user.get("lifetime_xp") or 0
    return {
        "points_balance": user["points_balance"],
        "referral_code": user["referral_code"],
        "ledger": ledger,
        "referrals": referrals,
        "referral_count": len(referrals),
        # added fields (existing ones above are unchanged)
        "lifetime_points_earned": lifetime,
        "earn_multiplier": earn_multiplier(lifetime),
        "next_multiplier_at": next_multiplier_at(lifetime),
        "min_redemption_points": MIN_REDEMPTION_POINTS,
        "kes_per_point_redeemed": KES_PER_POINT_REDEEMED,
        "max_redemption_percent_of_order": MAX_REDEMPTION_PERCENT_OF_ORDER,
    }


def redeem_points(user_id: str, points: int, order_total=None) -> dict:
    """Turns points into a discount code.
    order_total is optional: when the caller knows the order amount, the 30% cap is enforced now.
    (Otherwise the cap must be enforced when the code is applied at checkout.)"""
    if isinstance(points, bool) or not isinstance(points, int):
        raise RewardsError("Points must be a whole number")
    if points < MIN_REDEMPTION_POINTS:
        raise RewardsError(f"Minimum redemption is {MIN_REDEMPTION_POINTS} points")

    supabase = get_supabase()
    user_result = supabase.table("users").select("points_balance").eq("id", user_id).execute()
    if not user_result.data:
        raise RewardsError("User not found", 404)

    current_balance = user_result.data[0]["points_balance"] or 0
    if points > current_balance:
        raise RewardsError("You don't have enough points for that", 409)

    discount_value = round(points * KES_PER_POINT_REDEEMED, 2)
    if order_total is not None and discount_value > float(order_total) * MAX_REDEMPTION_PERCENT_OF_ORDER / 100:
        raise RewardsError(
            f"A code can cover at most {MAX_REDEMPTION_PERCENT_OF_ORDER}% of an order"
        )

    # Atomic: the balance only changes if it is still what we just read, so two
    # requests at the same moment cannot both spend the same points.
    new_balance = current_balance - points
    updated = (
        supabase.table("users")
        .update({"points_balance": new_balance})
        .eq("id", user_id)
        .eq("points_balance", current_balance)
        .execute()
    )
    if not updated.data:
        raise RewardsError("Your balance just changed, please try again", 409)

    code = _generate_discount_code()
    try:
        supabase.table("rewards_ledger").insert(
            {
                "user_id": user_id,
                "type": "redeem",
                "points": -points,
                "description": f"Redeemed for code {code} (KES {discount_value:g} off)",
            }
        ).execute()
    except Exception:
        # could not record it: give the points back rather than lose them
        latest = supabase.table("users").select("points_balance").eq("id", user_id).execute().data
        if latest:
            supabase.table("users").update(
                {"points_balance": (latest[0]["points_balance"] or 0) + points}
            ).eq("id", user_id).execute()
        raise

    return {
        "code": code,
        "discount_value": discount_value,
        "points_redeemed": points,
        "new_balance": new_balance,
        "max_order_percent": MAX_REDEMPTION_PERCENT_OF_ORDER,
    }