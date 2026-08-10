"""
Populates the badges table with starter badge definitions.
Run with: python seed_badges.py
Safe to re-run -- it checks for existing codes before inserting.

These are placeholder badges -- rename, add, or change unlock_criteria
freely once the real Mark system is designed. unlock_criteria supports:
  'first_order'   -> unlocked after 1+ orders
  'orders:N'      -> unlocked after N+ orders
  'referrals:N'   -> unlocked after N+ successful referrals
"""

from database.supabase_client import get_supabase

BADGES = [
    {
        "code": "first_order",
        "name": "First Mark",
        "description": "Placed your first ZALMA order.",
        "icon": "🏅",
        "unlock_criteria": "first_order",
    },
    {
        "code": "five_orders",
        "name": "Loyal Wearer",
        "description": "Placed 5 orders.",
        "icon": "👑",
        "unlock_criteria": "orders:5",
    },
    {
        "code": "first_referral",
        "name": "Circle Builder",
        "description": "Referred your first friend.",
        "icon": "🤝",
        "unlock_criteria": "referrals:1",
    },
    {
        "code": "five_referrals",
        "name": "Community Pillar",
        "description": "Referred 5 friends who made a purchase.",
        "icon": "🏛️",
        "unlock_criteria": "referrals:5",
    },
]


def seed():
    supabase = get_supabase()
    for b in BADGES:
        existing = supabase.table("badges").select("id").eq("code", b["code"]).execute()
        if existing.data:
            print(f"Skipping existing badge: {b['code']}")
            continue
        supabase.table("badges").insert(b).execute()
        print(f"Created badge: {b['code']}")
    print("Done.")


if __name__ == "__main__":
    seed()
