def public_ledger_entry(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "type": entry["type"],
        "points": entry["points"],
        "description": entry.get("description"),
        "order_id": entry.get("order_id"),
        "created_at": entry["created_at"],
    }


def public_referral(referral: dict, referred_user: dict = None) -> dict:
    return {
        "id": referral["id"],
        "referred_name": referred_user.get("name") if referred_user else None,
        "referred_email": referred_user.get("email") if referred_user else None,
        "reward_granted": referral["reward_granted"],
        "created_at": referral["created_at"],
    }
