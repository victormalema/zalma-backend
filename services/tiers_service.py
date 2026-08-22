from database.supabase_client import get_supabase

# ---------------------------------------------------------------
# TIER DEFINITIONS -- placeholder copy/thresholds, easy to tune.
# Each tier spans XP_PER_TIER points of lifetime_xp.
# ---------------------------------------------------------------
XP_PER_TIER = 1000

TIERS = [
    {"code": "initiate", "name": "Initiate", "tagline": "You have entered the world."},
    {"code": "collector", "name": "Collector", "tagline": "You don't follow pieces. You collect meaning."},
    {"code": "insider", "name": "Insider", "tagline": "You're no longer watching from outside."},
    {"code": "visionary", "name": "Visionary", "tagline": "You see what others haven't yet."},
    {"code": "icon", "name": "Icon", "tagline": "Recognized by the culture."},
    {"code": "legend", "name": "Legend", "tagline": "Your name lives beyond the moment."},
]


def tier_index_for_xp(xp: int) -> int:
    idx = xp // XP_PER_TIER
    return min(idx, len(TIERS) - 1)


def get_rank_status(user_id: str) -> dict:
    supabase = get_supabase()

    user_result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user_result.data:
        return {}
    user = user_result.data[0]

    lifetime_xp = user.get("lifetime_xp", 0)
    current_index = tier_index_for_xp(lifetime_xp)
    is_maxed = current_index == len(TIERS) - 1 and lifetime_xp >= (len(TIERS) - 1) * XP_PER_TIER

    orders_result = supabase.table("orders").select("id").eq("user_id", user_id).execute()
    drops = len(orders_result.data)

    from datetime import datetime, timezone
    member_since = user.get("created_at")
    days_active = 0
    if member_since:
        joined = datetime.fromisoformat(member_since.replace("Z", "+00:00"))
        days_active = (datetime.now(timezone.utc) - joined).days

    # Rank among all users, ordered by lifetime_xp (separate ranking from the points leaderboard)
    all_xp_result = supabase.table("users").select("id, lifetime_xp").execute()
    all_users = all_xp_result.data
    higher_count = sum(1 for u in all_users if u["lifetime_xp"] > lifetime_xp)
    rank = higher_count + 1
    total_members = len(all_users)

    # % of members holding EACH tier the user has reached, for the "held by X% of members" line
    tier_percentages = []
    for i in range(len(TIERS)):
        count_at_tier = sum(1 for u in all_users if tier_index_for_xp(u["lifetime_xp"]) == i)
        pct = round((count_at_tier / total_members) * 100, 1) if total_members else 0.0
        tier_percentages.append(pct)

    cards = []
    for i, tier in enumerate(TIERS):
        if i > current_index:
            status = "locked"
            progress = 0
        elif i == current_index and not (is_maxed and i == len(TIERS) - 1):
            status = "current"
            progress = lifetime_xp - (i * XP_PER_TIER)
        else:
            status = "complete"
            progress = XP_PER_TIER

        cards.append(
            {
                "position": i + 1,
                "total_tiers": len(TIERS),
                "code": tier["code"],
                "name": tier["name"],
                "tagline": tier["tagline"],
                "status": status,
                "progress_xp": progress,
                "xp_needed": XP_PER_TIER,
                "held_by_percent": tier_percentages[i],
            }
        )

    return {
        "lifetime_xp": lifetime_xp,
        "current_tier": TIERS[current_index]["code"],
        "drops": drops,
        "days_active": days_active,
        "rank": rank,
        "member_since": member_since,
        "cards": cards,
    }
