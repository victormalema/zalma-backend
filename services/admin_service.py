from database.supabase_client import get_supabase
from datetime import datetime, timedelta, timezone

VALID_STATUSES = ('pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled')


class AdminError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_dashboard_stats() -> dict:
    supabase = get_supabase()

    orders_result = supabase.table("orders").select("status, total, created_at").execute()
    orders = orders_result.data

    revenue = sum(float(o["total"]) for o in orders if o["status"] != "cancelled")
    status_counts = {}
    for o in orders:
        status_counts[o["status"]] = status_counts.get(o["status"], 0) + 1

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    orders_this_week = sum(1 for o in orders if o["created_at"] >= week_ago)

    users_result = supabase.table("users").select("id, created_at, points_balance").execute()
    users = users_result.data
    signups_this_week = sum(1 for u in users if u["created_at"] >= week_ago)

    ledger_result = supabase.table("rewards_ledger").select("points, type").execute()
    ledger = ledger_result.data
    points_issued = sum(e["points"] for e in ledger if e["points"] > 0)
    points_redeemed = sum(abs(e["points"]) for e in ledger if e["points"] < 0)

    pending_testimonials = (
        supabase.table("testimonials").select("id", count="exact").eq("approved", False).execute()
    )
    pending_unboxing = (
        supabase.table("unboxing_submissions").select("id", count="exact").eq("status", "pending").execute()
    )

    return {
        "total_revenue": round(revenue, 2),
        "total_orders": len(orders),
        "orders_this_week": orders_this_week,
        "orders_by_status": status_counts,
        "total_users": len(users),
        "signups_this_week": signups_this_week,
        "points_issued": points_issued,
        "points_redeemed": points_redeemed,
        "pending_testimonials_count": pending_testimonials.count or 0,
        "pending_unboxing_count": pending_unboxing.count or 0,
    }


def get_all_users() -> list:
    supabase = get_supabase()
    result = (
        supabase.table("users")
        .select("id, name, email, points_balance, lifetime_xp, referral_code, is_admin, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def get_all_orders() -> list:
    supabase = get_supabase()
    orders_result = supabase.table("orders").select("*").order("created_at", desc=True).execute()
    orders = orders_result.data
    if not orders:
        return []

    user_ids = list({o["user_id"] for o in orders})
    users_result = supabase.table("users").select("id, name, email").in_("id", user_ids).execute()
    users = {u["id"]: u for u in users_result.data}

    result = []
    for o in orders:
        user = users.get(o["user_id"], {})
        result.append({
            "id": o["id"],
            "status": o["status"],
            "subtotal": float(o["subtotal"]),
            "discount": float(o["discount"]),
            "total": float(o["total"]),
            "shipping_address": o["shipping_address"],
            "points_earned": o["points_earned"],
            "created_at": o["created_at"],
            "customer_name": user.get("name"),
            "customer_email": user.get("email"),
        })
    return result


def update_order_status(order_id: str, new_status: str) -> dict:
    if new_status not in VALID_STATUSES:
        raise AdminError(f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")

    supabase = get_supabase()
    result = supabase.table("orders").update({"status": new_status}).eq("id", order_id).execute()

    if not result.data:
        raise AdminError("Order not found", 404)

    return {"id": order_id, "status": new_status}
