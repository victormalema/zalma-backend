def public_wrap(wrap: dict) -> dict:
    return {
        "id": wrap["id"],
        "milestone_code": wrap["milestone_code"],
        "title": wrap["title"],
        "stats": wrap["stats"],
        "created_at": wrap["created_at"],
    }
