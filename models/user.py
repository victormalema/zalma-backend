def public_user(user: dict) -> dict:
    """Strips sensitive fields (password_hash) before a user record leaves the backend."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "phone": user.get("phone"),
        "address": user.get("address"),
        "referral_code": user.get("referral_code"),
        "points_balance": user.get("points_balance", 0),
        "created_at": user.get("created_at"),
    }
