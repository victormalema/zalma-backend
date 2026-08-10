def public_leaderboard_entry(user: dict, rank: int) -> dict:
    return {
        "rank": rank,
        "name": user.get("name") or "A ZALMA member",
        "points_balance": user["points_balance"],
    }


def public_testimonial(testimonial: dict, user: dict = None) -> dict:
    return {
        "id": testimonial["id"],
        "author_name": user.get("name") if user else None,
        "content": testimonial["content"],
        "image": testimonial.get("image"),
        "created_at": testimonial["created_at"],
    }
