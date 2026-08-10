from database.supabase_client import get_supabase
from models.wall import public_leaderboard_entry, public_testimonial


class WallError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_leaderboard(limit: int = 10) -> list:
    supabase = get_supabase()
    result = (
        supabase.table("users")
        .select("name, points_balance")
        .order("points_balance", desc=True)
        .limit(limit)
        .execute()
    )
    return [public_leaderboard_entry(u, i + 1) for i, u in enumerate(result.data)]


def get_testimonials() -> list:
    supabase = get_supabase()
    result = (
        supabase.table("testimonials")
        .select("*")
        .eq("approved", True)
        .order("created_at", desc=True)
        .execute()
    )
    testimonials = result.data
    if not testimonials:
        return []

    user_ids = [t["user_id"] for t in testimonials]
    users_result = supabase.table("users").select("id, name").in_("id", user_ids).execute()
    users = {u["id"]: u for u in users_result.data}

    return [public_testimonial(t, users.get(t["user_id"])) for t in testimonials]


def submit_testimonial(user_id: str, content: str, image: str = None) -> dict:
    if not content or not content.strip():
        raise WallError("content is required")
    if len(content.strip()) > 1000:
        raise WallError("content must be 1000 characters or fewer")

    supabase = get_supabase()
    result = (
        supabase.table("testimonials")
        .insert(
            {
                "user_id": user_id,
                "content": content.strip(),
                "image": image,
                "approved": False,
            }
        )
        .execute()
    )
    return {
        "submitted": True,
        "message": "Thanks -- your testimonial is pending review before it appears on the Wall.",
        "testimonial_id": result.data[0]["id"],
    }
