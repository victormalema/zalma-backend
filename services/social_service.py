from database.supabase_client import get_supabase

# ---------------------------------------------------------------
# PLACEHOLDER POINTS RATE -- matches the mock UI's "+25 pts" per platform.
# ---------------------------------------------------------------
POINTS_PER_FOLLOW = 25
VALID_PLATFORMS = ("instagram", "tiktok", "twitter")


class SocialError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _credit_points(supabase, user_id: str, points: int, description: str):
    user_result = supabase.table("users").select("points_balance, lifetime_xp").eq("id", user_id).execute()
    if not user_result.data:
        return
    current_balance = user_result.data[0]["points_balance"]
    current_xp = user_result.data[0].get("lifetime_xp", 0)
    supabase.table("users").update(
        {"points_balance": current_balance + points, "lifetime_xp": current_xp + points}
    ).eq("id", user_id).execute()
    supabase.table("rewards_ledger").insert(
        {"user_id": user_id, "type": "earn", "points": points, "description": description}
    ).execute()


def claim_follow(user_id: str, platform: str) -> dict:
    if platform not in VALID_PLATFORMS:
        raise SocialError("Unknown platform")

    supabase = get_supabase()

    existing = (
        supabase.table("social_follows")
        .select("id")
        .eq("user_id", user_id)
        .eq("platform", platform)
        .execute()
    )
    if existing.data:
        raise SocialError(f"Already claimed for {platform}", 409)

    supabase.table("social_follows").insert({"user_id": user_id, "platform": platform}).execute()
    _credit_points(supabase, user_id, POINTS_PER_FOLLOW, f"Followed ZALMA on {platform.capitalize()}")

    return {"platform": platform, "points_awarded": POINTS_PER_FOLLOW}


def get_claimed_platforms(user_id: str) -> list:
    supabase = get_supabase()
    result = supabase.table("social_follows").select("platform").eq("user_id", user_id).execute()
    return [r["platform"] for r in result.data]
