from database.supabase_client import get_supabase
from utils.validation import ValidationError, clean_https_url

MAX_PENDING_PER_USER = 3

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
    try:
        video_url = clean_https_url(video_url, label="video link")
    except ValidationError as e:
        raise UnboxingError(str(e))

    supabase = get_supabase()

    # Stop one video being submitted again (by anyone), and cap the review backlog per user.
    if supabase.table("unboxing_submissions").select("id").eq("video_url", video_url).limit(1).execute().data:
        raise UnboxingError("That video has already been submitted", 409)
    pending = (
        supabase.table("unboxing_submissions").select("id")
        .eq("user_id", user_id).eq("status", "pending").execute().data
    )
    if len(pending) >= MAX_PENDING_PER_USER:
        raise UnboxingError("You already have videos waiting for review. Please wait for them to be approved.", 429)

    result = (
        supabase.table("unboxing_submissions")
        .insert({"user_id": user_id, "video_url": video_url, "status": "pending"})
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
