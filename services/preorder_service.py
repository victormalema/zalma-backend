import re
import uuid
from datetime import datetime, timezone

from database.supabase_client import get_supabase
from models.preorder import public_preorder, public_preorder_item

MAX_QTY_PER_RESERVATION = 5


class PreorderError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------- helpers ----------

def _clean_uuid(value, label: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise PreorderError("Invalid " + label, 400)


def _normalize_phone(raw) -> str:
    digits = re.sub(r"[\s\-()]", "", str(raw or ""))
    m = re.fullmatch(r"(?:\+?254|0)([17]\d{8})", digits)
    if not m:
        raise PreorderError("Please enter a valid Kenyan phone number (e.g. 0712 345 678)")
    return "254" + m.group(1)


def _pick_option(value, allowed, label: str):
    """Size/colour must be one of the item's options (or None if the item has none)."""
    if not allowed:
        return None
    value = str(value).strip() if value else ""
    if value not in allowed:
        raise PreorderError("Please choose a " + label)
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _open_items_query(supabase):
    """Active items whose closing time hasn't passed (or has none)."""
    return (
        supabase.table("preorder_items")
        .select("*")
        .eq("is_active", True)
        .or_("closes_at.is.null,closes_at.gt." + _now_iso())
    )


def _get_open_item(supabase, item_id: str) -> dict:
    result = _open_items_query(supabase).eq("id", item_id).execute()
    if not result.data:
        raise PreorderError("This pre-order is closed or no longer available", 404)
    return result.data[0]


# ---------- public ----------

def get_open_items() -> list:
    supabase = get_supabase()
    result = _open_items_query(supabase).order("created_at").execute()
    return [public_preorder_item(i) for i in result.data]


# ---------- per user ----------

def get_my_preorders(user_id: str) -> list:
    supabase = get_supabase()
    rows = (
        supabase.table("preorders")
        .select("*")
        .eq("user_id", user_id)
        .neq("status", "cancelled")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    if not rows:
        return []

    item_ids = list({r["preorder_item_id"] for r in rows})
    items = {
        i["id"]: i
        for i in supabase.table("preorder_items").select("*").in_("id", item_ids).execute().data
    }
    return [public_preorder(r, items.get(r["preorder_item_id"])) for r in rows]


def create_preorder(user_id: str, data: dict) -> dict:
    supabase = get_supabase()

    item_id = _clean_uuid(data.get("preorder_item_id"), "item")
    item = _get_open_item(supabase, item_id)

    size = _pick_option(data.get("size"), item.get("sizes"), "size")
    color = _pick_option(data.get("color"), item.get("colors"), "colour")
    phone = _normalize_phone(data.get("phone"))

    try:
        qty = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        raise PreorderError("Invalid quantity")
    if not 1 <= qty <= MAX_QTY_PER_RESERVATION:
        raise PreorderError("Quantity must be between 1 and %d" % MAX_QTY_PER_RESERVATION)

    # Same person, same item/size/colour, still pending -> bump the quantity
    q = (
        supabase.table("preorders")
        .select("*")
        .eq("user_id", user_id)
        .eq("preorder_item_id", item_id)
        .eq("status", "pending")
    )
    q = q.eq("size", size) if size else q.is_("size", "null")
    q = q.eq("color", color) if color else q.is_("color", "null")
    existing = q.execute().data

    if existing:
        new_qty = existing[0]["quantity"] + qty
        if new_qty > MAX_QTY_PER_RESERVATION:
            raise PreorderError(
                "You can reserve up to %d of the same piece" % MAX_QTY_PER_RESERVATION
            )
        updated = (
            supabase.table("preorders")
            .update({"quantity": new_qty, "phone": phone})
            .eq("id", existing[0]["id"])
            .eq("user_id", user_id)
            .execute()
        )
        return public_preorder(updated.data[0], item)

    inserted = (
        supabase.table("preorders")
        .insert(
            {
                "user_id": user_id,
                "preorder_item_id": item_id,
                "size": size,
                "color": color,
                "quantity": qty,
                "phone": phone,
            }
        )
        .execute()
    )
    return public_preorder(inserted.data[0], item)


def cancel_preorder(user_id: str, preorder_id: str) -> None:
    supabase = get_supabase()
    preorder_id = _clean_uuid(preorder_id, "pre-order")

    result = (
        supabase.table("preorders")
        .select("id,status")
        .eq("id", preorder_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise PreorderError("Pre-order not found", 404)
    if result.data[0]["status"] != "pending":
        raise PreorderError("Only pending pre-orders can be cancelled", 400)

    supabase.table("preorders").update({"status": "cancelled"}).eq("id", preorder_id).eq(
        "user_id", user_id
    ).execute()
