from database.supabase_client import get_supabase
from models.badge import public_badge


def _user_stats(supabase, user_id: str) -> dict:
    orders_result = supabase.table("orders").select("id").eq("user_id", user_id).execute()
    referrals_result = (
        supabase.table("referrals")
        .select("id")
        .eq("referrer_id", user_id)
        .eq("reward_granted", True)
        .execute()
    )
    return {
        "orders_count": len(orders_result.data),
        "referrals_count": len(referrals_result.data),
    }


def _criteria_met(criteria: str, stats: dict) -> bool:
    """
    Supported criteria formats (stored as plain text on the badge row):
      'first_order'    -> unlocked after 1+ orders
      'orders:N'       -> unlocked after N+ orders
      'referrals:N'    -> unlocked after N+ successful referrals
    """
    if not criteria:
        return False
    if criteria == "first_order":
        return stats["orders_count"] >= 1
    if criteria.startswith("orders:"):
        threshold = int(criteria.split(":")[1])
        return stats["orders_count"] >= threshold
    if criteria.startswith("referrals:"):
        threshold = int(criteria.split(":")[1])
        return stats["referrals_count"] >= threshold
    return False


def check_and_unlock_badges(user_id: str) -> list:
    """Call this after events that could unlock a badge (order placed, referral completed).
    Returns any badges newly unlocked in this call."""
    supabase = get_supabase()

    all_badges = supabase.table("badges").select("*").execute().data
    if not all_badges:
        return []

    unlocked_result = (
        supabase.table("user_badges").select("badge_id").eq("user_id", user_id).execute()
    )
    already_unlocked_ids = {u["badge_id"] for u in unlocked_result.data}

    stats = _user_stats(supabase, user_id)

    newly_unlocked = []
    for badge in all_badges:
        if badge["id"] in already_unlocked_ids:
            continue
        if _criteria_met(badge.get("unlock_criteria"), stats):
            supabase.table("user_badges").insert(
                {"user_id": user_id, "badge_id": badge["id"]}
            ).execute()
            newly_unlocked.append(badge)

    return newly_unlocked


def get_user_badges(user_id: str) -> list:
    supabase = get_supabase()

    all_badges = supabase.table("badges").select("*").order("name").execute().data

    unlocked_result = (
        supabase.table("user_badges").select("*").eq("user_id", user_id).execute()
    )
    unlocked_map = {u["badge_id"]: u["unlocked_at"] for u in unlocked_result.data}

    return [
        public_badge(badge, badge["id"] in unlocked_map, unlocked_map.get(badge["id"]))
        for badge in all_badges
    ]
