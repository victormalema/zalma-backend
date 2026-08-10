def public_badge(badge: dict, unlocked: bool, unlocked_at: str = None) -> dict:
    return {
        "id": badge["id"],
        "code": badge["code"],
        "name": badge["name"],
        "description": badge.get("description"),
        "icon": badge.get("icon"),
        "unlocked": unlocked,
        "unlocked_at": unlocked_at,
    }
