from database.supabase_client import get_supabase

# ---------------------------------------------------------------
# PLACEHOLDER POINTS RATE -- matches the mock UI's "Earn 75 pts".
# Points are only credited once an admin approves the submission --
# that crediting step lives in the admin panel, not here.
# ---------------------------------------------------------------
POINTS_PER_UNBOXING = 75


class UnboxingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def submit_unboxing(user_id: str, video_url: str) -> dict:
    if not video_url or not video_url.strip():
        raise UnboxingError("A video URL is required")

    supabase = get_supabase()
    result = (
        supabase.table("unboxing_submissions")
        .insert({"user_id": user_id, "video_url": video_url.strip(), "status": "pending"})
        .execute()
    )
    return {
        "submitted": True,
        "id": result.data[0]["id"],
        "message": "Thanks! Your unboxing video is pending review. You'll earn points once it's approved.",
    }


def get_user_unboxings(user_id: str) -> list:
    supabase = get_supabase()
    result = (
        supabase.table("unboxing_submissions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data
