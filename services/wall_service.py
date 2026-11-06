from database.supabase_client import get_supabase
from models.wall import public_leaderboard_entry, public_testimonial
from utils.validation import ValidationError, clean_https_url


class WallError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_leaderboard(limit: int = 10) -> list:
    supabase = get_supabase()
    result = (
        supabase.table("users")
        .select("id,name, points_balance")
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
    if content is None or content == "":
        raise WallError("content is required")

    if not isinstance(content, str):
        raise WallError("content must be text")

    content = content.strip()

    if not content:
        raise WallError("content is required")

    if len(content) > 1000:
        raise WallError("content must be 1000 characters or fewer")

    if image:
        try:
            image = clean_https_url(image, label="image link")
        except ValidationError as e:
            raise WallError(str(e))
    else:
        image = None

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
def get_pending_testimonials() -> list:
    supabase = get_supabase()
    result = (
        supabase.table("testimonials")
        .select("*")
        .eq("approved", False)
        .order("created_at", desc=True)
        .execute()
    )
    testimonials = result.data
    if not testimonials:
        return []

    user_ids = [t["user_id"] for t in testimonials]
    users_result = supabase.table("users").select("id, name, email").in_("id", user_ids).execute()
    users = {u["id"]: u for u in users_result.data}

    return [public_testimonial(t, users.get(t["user_id"])) for t in testimonials]


def moderate_testimonial(testimonial_id: str, approve: bool) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("testimonials")
        .update({"approved": approve})
        .eq("id", testimonial_id)
        .execute()
    )
    if not result.data:
        raise WallError("Testimonial not found", 404)
    return {"id": testimonial_id, "approved": approve}
