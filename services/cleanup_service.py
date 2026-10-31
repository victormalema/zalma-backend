"""
services/cleanup_service.py
Frees stock held by orders whose payment was never completed.

An order stays 'pending' from checkout until M-Pesa reports back. If the customer
ignores the prompt or the callback never arrives, the stock stays reserved forever.
This releases it:

  * pending for more than ABANDONED_AFTER_MINUTES
      - never got a prompt (no checkout_request_id)  -> cancelled, stock returned
      - got a prompt -> we ask Safaricom (STK query) what happened:
          paid          -> marked paid (the callback was lost)
          failed/timeout-> cancelled, stock returned
          no answer yet -> left alone, retried next time
            (cancelled anyway after GIVE_UP_AFTER_HOURS)

It runs on its own whenever someone checks out or the admin opens Orders (at most
every 5 minutes), and can also be triggered by an outside timer (see payments_routes).
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from database.supabase_client import get_supabase
from services.mpesa_service import MpesaError, stk_query
from services.orders_service import cancel_unpaid_order, complete_order_after_payment

log = logging.getLogger(__name__)

ABANDONED_AFTER_MINUTES = 30
GIVE_UP_AFTER_HOURS = 24
MIN_SECONDS_BETWEEN_RUNS = 300

_last_run = 0.0


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def release_abandoned_orders() -> dict:
    """Does one cleanup pass. Returns counts: {"cancelled": n, "marked_paid": n, "skipped": n}."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    stale = (
        supabase.table("orders").select("*")
        .eq("status", "pending")
        .lt("created_at", _iso(now - timedelta(minutes=ABANDONED_AFTER_MINUTES)))
        .execute().data
    )
    very_old_ids = {
        o["id"] for o in
        supabase.table("orders").select("id")
        .eq("status", "pending")
        .lt("created_at", _iso(now - timedelta(hours=GIVE_UP_AFTER_HOURS)))
        .execute().data
    }

    counts = {"cancelled": 0, "marked_paid": 0, "skipped": 0}

    for order in stale:
        outcome = "cancel"
        request_id = order.get("checkout_request_id")

        if request_id:
            try:
                answer = stk_query(request_id)
            except MpesaError as e:
                log.warning("STK query failed for order %s: %s", order["id"], e.message)
                answer = {"result_code": None}

            if answer["result_code"] == 0:
                outcome = "paid"
            elif answer["result_code"] is None and order["id"] not in very_old_ids:
                counts["skipped"] += 1
                continue   # no answer yet: try again on the next run
            elif answer["result_code"] is None:
                log.warning("Order %s: no answer from M-Pesa after %sh, cancelling", order["id"], GIVE_UP_AFTER_HOURS)

        if outcome == "paid":
            # The callback was lost but the customer did pay. (The receipt number is
            # not part of the query answer, so find it in your M-Pesa statement.)
            won = (
                supabase.table("orders")
                .update({"status": "paid", "paid_at": _iso(now)})
                .eq("id", order["id"]).eq("status", "pending").execute()
            )
            if won.data:
                complete_order_after_payment(order["id"])
                counts["marked_paid"] += 1
        else:
            won = (
                supabase.table("orders")
                .update({"status": "payment_failed"})
                .eq("id", order["id"]).eq("status", "pending").execute()
            )
            if won.data:
                cancel_unpaid_order(order["id"])   # give the reserved stock back
                counts["cancelled"] += 1

    if any(counts.values()):
        log.info("Abandoned-order cleanup: %s", counts)
    return counts


def run_cleanup_if_due():
    """Cheap to call often: runs at most once every few minutes and never raises."""
    global _last_run
    if time.time() - _last_run < MIN_SECONDS_BETWEEN_RUNS:
        return None
    _last_run = time.time()
    try:
        return release_abandoned_orders()
    except Exception:
        log.exception("Abandoned-order cleanup failed")
        return None
