"""
services/rewards_config.py
Single source of truth for every rewards number.

NOTE: named rewards_config.py inside services/ -- NOT config/rewards.py. The project
already has config.py, and creating a config/ folder would shadow it and break app.py.

Change a number here and the backend follows. (Front-end tiles still show text, see notes.)
"""
import math

# ---------------------------------------------------------------
# Earning: purchases (the main way to earn)
# ---------------------------------------------------------------
POINTS_PER_KES_SPENT = 0.01      # 1 point per KES 100 of goods (delivery is not counted)
MAX_POINTS_PER_ORDER = 5000      # hard cap per order

# Earn multiplier by LIFETIME points earned (lifetime points never go down,
# so redeeming never lowers it). Applies to earning only, never to redemption.
EARN_MULTIPLIERS = [
    (0, 1.00),
    (1000, 1.10),
    (5000, 1.25),
    (20000, 1.50),
]

# ---------------------------------------------------------------
# Earning: referrals
# ---------------------------------------------------------------
REFERRAL_FIRST_PURCHASE_POINTS = 300   # paid to the referrer when the friend's first order is paid
REFERRAL_SIGNUP_POINTS = 0             # not paid: see notes (needs auth_service.py, and invites fake-account farming)
REFERRAL_MAX_PER_YEAR = 10             # referral rewards one person can earn per rolling 365 days

# ---------------------------------------------------------------
# Earning: engagement (kept small on purpose -- NOT wired yet, needs social/unboxing services)
# ---------------------------------------------------------------
SOCIAL_FOLLOW_POINTS = 10              # per platform, one time
UNBOXING_POINTS = 75                   # admin-approved video of a real order

# ---------------------------------------------------------------
# Redemption
# ---------------------------------------------------------------
KES_PER_POINT_REDEEMED = 0.5           # 100 points = KES 50 off
MIN_REDEMPTION_POINTS = 200            # 200 points = KES 100 off
MAX_REDEMPTION_PERCENT_OF_ORDER = 30   # a code may cover at most 30% of an order
POINTS_EXPIRY_DAYS = 365               # not enforced yet (needs a nightly job)


def earn_multiplier(lifetime_points) -> float:
    """Multiplier for someone who has earned `lifetime_points` in total."""
    lifetime_points = lifetime_points or 0
    current = 1.0
    for threshold, mult in EARN_MULTIPLIERS:
        if lifetime_points >= threshold:
            current = mult
    return current


def next_multiplier_at(lifetime_points):
    """Lifetime points needed for the next multiplier level, or None at the top."""
    lifetime_points = lifetime_points or 0
    for threshold, _ in EARN_MULTIPLIERS:
        if threshold > lifetime_points:
            return threshold
    return None


def purchase_points(spend_kes, lifetime_points=0) -> int:
    """Points for an order: goods spend x rate x multiplier, rounded down, capped per order."""
    base = float(spend_kes or 0) * POINTS_PER_KES_SPENT * earn_multiplier(lifetime_points)
    return max(0, min(MAX_POINTS_PER_ORDER, int(math.floor(round(base, 6)))))
