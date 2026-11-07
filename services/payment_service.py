"""
services/payment_service.py
Ties M-Pesa to orders: start a payment, handle Safaricom's callback, report status.
"""
import logging
import math
from datetime import datetime, timezone

from database.supabase_client import get_supabase
from services.mpesa_service import normalize_phone, parse_callback, stk_push
from services.orders_service import OrderError, cancel_unpaid_order, complete_order_after_payment

log = logging.getLogger(__name__)

# Statuses that mean "payment went through"
PAID_STATUSES = ("paid", "shipped", "delivered")


def _get_user_order(supabase, user_id: str, order_id: str) -> dict:
    result = supabase.table("orders").select("*").eq("id", order_id).eq("user_id", user_id).execute()
    if not result.data:
        raise OrderError("Order not found", 404)
    return result.data[0]


def initiate_payment(user_id: str, order_id: str, phone: str) -> dict:
    """Sends the M-Pesa PIN prompt for a pending order."""
    supabase = get_supabase()
    order = _get_user_order(supabase, user_id, order_id)
    if order["status"] != "pending":
        raise OrderError("This order is not waiting for payment", 409)

    phone = normalize_phone(phone)                       # raises MpesaError(400) if invalid
    push = stk_push(phone, order["total"], order["id"])  # raises MpesaError if Safaricom rejects

    supabase.table("orders").update(
        {"checkout_request_id": push["checkout_request_id"], "payment_phone": phone}
    ).eq("id", order["id"]).execute()

    return {"message": push["customer_message"], "order_id": order["id"]}


def handle_callback(body: dict):
    """Safaricom calls this once the customer pays, cancels, or the prompt times out.
    Safe to call twice for the same payment (duplicates are ignored)."""
    result = parse_callback(body)
    supabase = get_supabase()

    found = (
        supabase.table("orders").select("*")
        .eq("checkout_request_id", result["checkout_request_id"]).execute()
    )
    if not found.data:
        log.warning("M-Pesa callback for unknown CheckoutRequestID %s", result["checkout_request_id"])
        return
    order = found.data[0]

    if result["result_code"] == 0:
        # Real-money safety check: the amount M-Pesa collected must cover the order.
        # (We always ask for the order total rounded up to whole shillings.)
        expected = math.ceil(float(order["total"]))
        if result["amount"] is not None and float(result["amount"]) < expected:
            log.error(
                "M-Pesa amount mismatch for order %s: paid %s, expected %s -- left pending for review",
                order["id"], result["amount"], expected,
            )
            return

        # Atomic: only the first callback flips pending -> paid
        won = (
            supabase.table("orders")
            .update({"status": "paid", "mpesa_receipt": result["receipt"], "paid_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", order["id"]).eq("status", "pending").execute()
        )
        if won.data:
            complete_order_after_payment(order["id"])
    else:
        processed = cancel_unpaid_order(order["id"])
        log.info(
            "M-Pesa payment not completed for order %s: %s (failure processed: %s)",
            order["id"],
            result["result_desc"],
            processed,
        )


def get_payment_status(user_id: str, order_id: str) -> dict:
    """What the checkout page polls while the customer is entering their PIN."""
    order = _get_user_order(get_supabase(), user_id, order_id)
    status = order["status"]
    return {
        "order_id": order["id"],
        "status": status,
        "paid": status in PAID_STATUSES,
        "failed": status == "payment_failed",
        "receipt": order.get("mpesa_receipt"),
    }