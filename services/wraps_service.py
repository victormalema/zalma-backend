from typing import Optional
from database.supabase_client import get_supabase
from models.wrap import public_wrap


def _gather_stats(supabase, user_id: str) -> dict:
    user_result = supabase.table("users").select("*").eq("id", user_id).execute()
    user = user_result.data[0] if user_result.data else {}

    orders_result = supabase.table("orders").select("id").eq("user_id", user_id).execute()
    referrals_result = (
        supabase.table("referrals")
        .select("id")
        .eq("referrer_id", user_id)
        .eq("reward_granted", True)
        .execute()
    )
    badges_result = supabase.table("user_badges").select("id").eq("user_id", user_id).execute()

    return {
        "points_balance": user.get("points_balance", 0),
        "orders_count": len(orders_result.data),
        "referrals_count": len(referrals_result.data),
        "badges_count": len(badges_result.data),
        "member_since": user.get("created_at"),
    }


def generate_wrap(user_id: str, milestone_code: str, title: str) -> Optional[dict]:
    """
    Creates a wrap card snapshot for this milestone, if one doesn't already
    exist for this user (one card per milestone, ever -- that's what makes
    it a collectible history rather than something that keeps regenerating).
    Returns the new wrap dict, or None if one already existed.
    """
    supabase = get_supabase()

    existing = (
        supabase.table("wrap_cards")
        .select("id")
        .eq("user_id", user_id)
        .eq("milestone_code", milestone_code)
        .execute()
    )
    if existing.data:
        return None

    stats = _gather_stats(supabase, user_id)

    result = (
        supabase.table("wrap_cards")
        .insert(
            {
                "user_id": user_id,
                "milestone_code": milestone_code,
                "title": title,
                "stats": stats,
            }
        )
        .execute()
    )
    return public_wrap(result.data[0])


def get_user_wraps(user_id: str) -> list:
    supabase = get_supabase()
    result = (
        supabase.table("wrap_cards")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return [public_wrap(w) for w in result.data]

