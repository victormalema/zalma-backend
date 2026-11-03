"""
services/referral_service.py
Referral rewards. One referral pays the referrer twice:

  1) a small reward when the friend signs up with their code   (key  ref_signup:<friend id>)
  2) a bigger reward when that friend's first order is paid    (key  ref_purchase:<friend id>)

Each key can only ever be paid once. A referrer earns rewards for at most
REFERRAL_MAX_PER_YEAR friends in any rolling 365 days.

The signup reward is paid in two ways so it can never be missed:
  * award_signup_for_user(friend_id)   -> call it right after a sign-up creates the referral (optional, instant)
  * sweep_signup_bonuses(referrer_id)  -> runs whenever the referrer's rewards are loaded (catches everything else)
"""
import re
from datetime import datetime, timedelta

from database.supabase_client import get_supabase
from services.points_service import award_points
from services.rewards_config import (
    REFERRAL_FIRST_PURCHASE_POINTS,
    REFERRAL_MAX_PER_YEAR,
    REFERRAL_SIGNUP_POINTS,
    REFERRAL_SIGNUP_REWARDS_FROM,
)


def _parse(ts: str) -> datetime:
    """Reads a Supabase timestamp. Python 3.9 only accepts 3 or 6 fractional digits, so pad/trim them."""
    ts = (ts or "").strip().replace("Z", "+00:00")
    m = re.match(r"^(.*?)(\.\d+)?([+-]\d{2}:\d{2})?$", ts)
    base, frac, tz = m.group(1), m.group(2), m.group(3) or "+00:00"
    if frac:
        frac = (frac + "000000")[:7]
    return datetime.fromisoformat(base + (frac or "") + tz)


def _within_yearly_limit(supabase, referral: dict) -> bool:
    """True if this friend is among the referrer's first N friends in the 365 days up to their sign-up."""
    created = referral.get("created_at")
    if not created:
        return True
    since = (_parse(created) - timedelta(days=365)).isoformat()
    rows = (
        supabase.table("referrals").select("id, created_at")
        .eq("referrer_id", referral["referrer_id"]).gte("created_at", since)
        .execute().data
    )
    position = sum(1 for r in rows if r["created_at"] <= created)
    return position <= REFERRAL_MAX_PER_YEAR


def award_signup_bonus(referral: dict) -> dict:
    if not REFERRAL_SIGNUP_POINTS:
        return {"awarded": False, "reason": "disabled"}
    created = referral.get("created_at")
    if created and _parse(created) < _parse(REFERRAL_SIGNUP_REWARDS_FROM):
        return {"awarded": False, "reason": "joined_before_start"}
    if not _within_yearly_limit(get_supabase(), referral):
        return {"awarded": False, "reason": "yearly_limit"}
    return award_points(
        referral["referrer_id"], REFERRAL_SIGNUP_POINTS, kind="referral",
        description="Referral bonus -- a friend joined with your code",
        idempotency_key=f"ref_signup:{referral['referred_id']}",
    )


def award_purchase_bonus(referral: dict) -> dict:
    if not _within_yearly_limit(get_supabase(), referral):
        return {"awarded": False, "reason": "yearly_limit"}
    return award_points(
        referral["referrer_id"], REFERRAL_FIRST_PURCHASE_POINTS, kind="referral",
        description="Referral bonus -- your invite made their first purchase",
        idempotency_key=f"ref_purchase:{referral['referred_id']}",
    )


def award_signup_for_user(referred_id: str) -> dict:
    """Optional instant hook: call right after a new user's referral row is created."""
    rows = get_supabase().table("referrals").select("*").eq("referred_id", referred_id).execute().data
    if not rows:
        return {"awarded": False, "reason": "no_referral"}
    return award_signup_bonus(rows[0])


def sweep_signup_bonuses(referrer_id: str) -> int:
    """Pays any signup rewards this referrer has not been paid yet. Returns how many were paid."""
    if not REFERRAL_SIGNUP_POINTS:
        return 0
    supabase = get_supabase()
    referrals = supabase.table("referrals").select("*").eq("referrer_id", referrer_id).execute().data
    if not referrals:
        return 0
    already = {
        r.get("idempotency_key")
        for r in supabase.table("rewards_ledger").select("idempotency_key")
        .eq("user_id", referrer_id).eq("type", "referral").execute().data
    }
    paid = 0
    for referral in referrals:
        if f"ref_signup:{referral['referred_id']}" in already:
            continue
        if award_signup_bonus(referral).get("awarded"):
            paid += 1
    return paid
