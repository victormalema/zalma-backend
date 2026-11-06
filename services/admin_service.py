from database.supabase_client import get_supabase
from datetime import datetime, timedelta, timezone
import uuid

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


# ---------- pre-orders ----------

PREORDER_STATUSES = ('pending', 'confirmed', 'fulfilled', 'cancelled')
# What a reservation may be changed to from each state
PREORDER_NEXT = {
    'pending': ('confirmed', 'cancelled'),
    'confirmed': ('fulfilled', 'cancelled'),
    'fulfilled': (),
    'cancelled': (),
}


def _clean_uuid(value, label: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise AdminError("Invalid " + label)


def get_all_preorders() -> dict:
    """Every reservation (with customer + item details) and every pre-order item."""
    supabase = get_supabase()

    rows = supabase.table("preorders").select("*").order("created_at", desc=True).execute().data
    items_data = (
        supabase.table("preorder_items").select("*").order("created_at", desc=True).execute().data
    )
    items = {i["id"]: i for i in items_data}

    users = {}
    user_ids = list({r["user_id"] for r in rows})
    if user_ids:
        users_result = supabase.table("users").select("id, name, email").in_("id", user_ids).execute()
        users = {u["id"]: u for u in users_result.data}

    reserved_units = {}
    preorders = []
    for r in rows:
        item = items.get(r["preorder_item_id"], {})
        user = users.get(r["user_id"], {})
        if r["status"] != "cancelled":
            reserved_units[r["preorder_item_id"]] = (
                reserved_units.get(r["preorder_item_id"], 0) + (r.get("quantity") or 0)
            )
        preorders.append({
            "id": r["id"],
            "status": r["status"],
            "quantity": r.get("quantity"),
            "size": r.get("size"),
            "color": r.get("color"),
            "phone": r.get("phone"),
            "created_at": r["created_at"],
            "item_name": item.get("name"),
            "lot_label": item.get("lot_label"),
            "customer_name": user.get("name"),
            "customer_email": user.get("email"),
        })

    item_list = [
        {
            "id": i["id"],
            "name": i["name"],
            "price": i["price"],
            "lot_label": i.get("lot_label"),
            "closes_at": i.get("closes_at"),
            "is_active": i["is_active"],
            "reserved_units": reserved_units.get(i["id"], 0),
        }
        for i in items_data
    ]
    return {"preorders": preorders, "items": item_list}


def update_preorder_status(preorder_id: str, new_status: str) -> dict:
    preorder_id = _clean_uuid(preorder_id, "pre-order")
    if new_status not in PREORDER_STATUSES:
        raise AdminError("Invalid status. Must be one of: " + ", ".join(PREORDER_STATUSES))

    supabase = get_supabase()
    current = supabase.table("preorders").select("status").eq("id", preorder_id).execute().data
    if not current:
        raise AdminError("Pre-order not found", 404)

    old_status = current[0]["status"]
    if new_status != old_status:
        if new_status not in PREORDER_NEXT.get(old_status, ()):
            raise AdminError("A %s pre-order can't be changed to %s" % (old_status, new_status))
        supabase.table("preorders").update({"status": new_status}).eq("id", preorder_id).execute()

    return {"id": preorder_id, "status": new_status}


def set_preorder_item_active(item_id: str, is_active) -> dict:
    item_id = _clean_uuid(item_id, "item")
    if not isinstance(is_active, bool):
        raise AdminError("is_active must be true or false")

    supabase = get_supabase()
    result = supabase.table("preorder_items").update({"is_active": is_active}).eq("id", item_id).execute()
    if not result.data:
        raise AdminError("Item not found", 404)
    return {"id": item_id, "is_active": is_active}
