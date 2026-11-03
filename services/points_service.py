"""
services/points_service.py
The ONE place that adds points to a user.

  * idempotent: pass an idempotency_key and the same award can never be paid twice
    (needs the unique index from rewards_points.sql)
  * safe under concurrency: the balance is only changed if nobody else changed it in between
  * lifetime_xp grows by the same amount and never goes down, so ranks are never demoted
"""
from database.supabase_client import get_supabase


def _is_duplicate(err: Exception) -> bool:
    text = str(err).lower()
    return "23505" in text or "duplicate key" in text or "unique constraint" in text


def award_points(user_id: str, points: int, *, kind: str, description: str,
                 order_id: str = None, idempotency_key: str = None) -> dict:
    """Returns {"awarded": bool, "points": int, "balance": int | None, "reason": str | None}."""
    if not points or points <= 0:
        return {"awarded": False, "points": 0, "balance": None, "reason": "nothing_to_award"}

    supabase = get_supabase()
    if not supabase.table("users").select("id").eq("id", user_id).execute().data:
        return {"awarded": False, "points": 0, "balance": None, "reason": "user_not_found"}

    entry = {
        "user_id": user_id,
        "type": kind,
        "points": points,
        "description": description,
        "order_id": order_id,
    }
    if idempotency_key:
        entry["idempotency_key"] = idempotency_key

    # 1) Write the ledger row first. With a key, the unique index makes a repeat fail here.
    try:
        inserted = supabase.table("rewards_ledger").insert(entry).execute()
    except Exception as err:
        if idempotency_key and _is_duplicate(err):
            return {"awarded": False, "points": 0, "balance": None, "reason": "already_awarded"}
        raise
    ledger_id = inserted.data[0].get("id") if inserted.data else None

    def _undo_ledger():
        if ledger_id:
            supabase.table("rewards_ledger").delete().eq("id", ledger_id).execute()

    # 2) Add to the balance. The update only applies if the balance is still what we read.
    for _ in range(5):
        rows = supabase.table("users").select("points_balance, lifetime_xp").eq("id", user_id).execute().data
        if not rows:
            _undo_ledger()
            return {"awarded": False, "points": 0, "balance": None, "reason": "user_not_found"}
        balance = rows[0].get("points_balance") or 0
        xp = rows[0].get("lifetime_xp") or 0
        done = (
            supabase.table("users")
            .update({"points_balance": balance + points, "lifetime_xp": xp + points})
            .eq("id", user_id)
            .eq("points_balance", balance)
            .execute()
        )
        if done.data:
            return {"awarded": True, "points": points, "balance": balance + points, "reason": None}

    _undo_ledger()
    raise RuntimeError("Could not update the points balance, please try again")
