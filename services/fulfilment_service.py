"""
services/fulfilment_service.py
Rules for moving an order through fulfilment + printable QR card data.

Money rules this enforces:
  * only the M-Pesa callback may mark an order paid (pending -> paid),
    so the admin page can never ship an unpaid order
  * orders only move forward: paid -> processing -> shipped -> delivered
"""
import io
import os
import secrets

import segno

from database.supabase_client import get_supabase

# What an admin may change an order TO, by its current status.
ALLOWED_TRANSITIONS = {
    "pending": [],                       # only the M-Pesa callback can change this
    "payment_failed": [],
    "paid": ["processing", "shipped", "cancelled"],
    "processing": ["shipped", "cancelled"],
    "shipped": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

# A card can be printed once payment is confirmed.
PRINTABLE_STATUSES = ("paid", "processing", "shipped", "delivered")


class FulfilmentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _get_order(order_id: str) -> dict:
    result = get_supabase().table("orders").select("*").eq("id", order_id).execute()
    if not result.data:
        raise FulfilmentError("Order not found", 404)
    return result.data[0]


def check_status_change(order_id: str, new_status: str):
    """Raises FulfilmentError if the admin may not move this order to new_status."""
    order = _get_order(order_id)
    current = order["status"]
    if new_status == current:
        return
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        if current in ("pending", "payment_failed"):
            raise FulfilmentError("This order has not been paid, so it cannot be changed.")
        raise FulfilmentError(f"An order that is '{current}' cannot be changed to '{new_status}'.")


def get_order_qr(order_id: str) -> dict:
    """Data for the printed card: claim link, short code and the QR as inline SVG."""
    supabase = get_supabase()
    order = _get_order(order_id)
    if order["status"] not in PRINTABLE_STATUSES:
        raise FulfilmentError("Cards can only be printed for paid orders.")

    token = order.get("qr_token")
    if not token:
        # Orders placed before this feature have no token yet: create one now (once).
        supabase.table("orders").update({"qr_token": secrets.token_urlsafe(12)}) \
            .eq("id", order_id).is_("qr_token", "null").execute()
        token = _get_order(order_id)["qr_token"]

    frontend = os.environ.get("FRONTEND_URL", "https://zalma-frontend.onrender.com").rstrip("/")
    url = f"{frontend}/home.html?claim={token}"

    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2, xmldecl=False, nl=False)

    return {
        "order_id": order["id"],
        "short_id": str(order["id"])[:8],
        "code": token,
        "url": url,
        "claimed": bool(order.get("qr_claimed_at")),
        "svg": buf.getvalue().decode("utf-8"),
    }
