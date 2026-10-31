import secrets
from datetime import datetime, timezone

from database.supabase_client import get_supabase
from services.cart_service import get_cart
from services.badges_service import check_and_unlock_badges
from models.order import public_order, public_order_item

# ---------------------------------------------------------------
# PLACEHOLDER REWARD RATES -- not finalized yet.
# Update these two numbers once the real rewards structure is decided,
# nothing else needs to change.
# ---------------------------------------------------------------
KES_PER_POINT = 100        # 1 point earned per 100 KES spent
REFERRAL_BONUS_POINTS = 200  # flat bonus to the referrer on the referred user's first order

# Delivery pricing (flat): Nairobi county vs everywhere else.
DELIVERY_FEE_NAIROBI = 200
DELIVERY_FEE_OTHER = 350


def _delivery_fee(shipping_address: str) -> int:
    """The checkout page saves the address as
    'Name, Tel: ..., Location, County, Postal Code, Country'. The county comes from a
    fixed dropdown, so it is the third item from the end."""
    parts = [p.strip() for p in (shipping_address or "").split(",")]
    county = parts[-3].lower() if len(parts) >= 3 else ""
    return DELIVERY_FEE_NAIROBI if county == "nairobi" else DELIVERY_FEE_OTHER


class OrderError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _credit_points(supabase, user_id: str, points: int, ptype: str, description: str, order_id: str = None):
    """Adds points to a user's balance and logs the transaction.
    Also grows lifetime_xp by the same amount -- xp only ever goes up,
    even if points later get redeemed, so rank never gets demoted."""
    user_result = supabase.table("users").select("points_balance, lifetime_xp").eq("id", user_id).execute()
    if not user_result.data:
        return
    current_balance = user_result.data[0]["points_balance"]
    current_xp = user_result.data[0].get("lifetime_xp", 0)
    supabase.table("users").update(
        {"points_balance": current_balance + points, "lifetime_xp": current_xp + points}
    ).eq("id", user_id).execute()
    supabase.table("rewards_ledger").insert(
        {
            "user_id": user_id,
            "type": ptype,
            "points": points,
            "description": description,
            "order_id": order_id,
        }
    ).execute()


def _maybe_grant_referral_bonus(supabase, user_id: str):
    """If this was the user's first order and they were referred, credit the referrer once."""
    orders_result = supabase.table("orders").select("id, status").eq("user_id", user_id).execute()
    paid_orders = [o for o in orders_result.data if o["status"] not in ("pending", "payment_failed")]
    if len(paid_orders) != 1:
        return  # not their first paid order

    referral_result = (
        supabase.table("referrals")
        .select("*")
        .eq("referred_id", user_id)
        .eq("reward_granted", False)
        .execute()
    )
    if not referral_result.data:
        return

    referral = referral_result.data[0]
    _credit_points(
        supabase,
        referral["referrer_id"],
        REFERRAL_BONUS_POINTS,
        "referral",
        "Referral bonus -- your invite made their first purchase",
    )
    supabase.table("referrals").update({"reward_granted": True}).eq("id", referral["id"]).execute()
    check_and_unlock_badges(referral["referrer_id"])


def checkout(user_id: str, shipping_address: str) -> dict:
    if not shipping_address or not shipping_address.strip():
        raise OrderError("Delivery address is required")

    supabase = get_supabase()

    cart = get_cart(user_id)
    if not cart["items"]:
        raise OrderError("Your cart is empty")

    product_ids = [item["product_id"] for item in cart["items"]]
    products_result = supabase.table("products").select("*").in_("id", product_ids).execute()
    products = {p["id"]: p for p in products_result.data}

    # Re-validate stock right before committing -- it may have changed
    # since the cart was last viewed.
    for item in cart["items"]:
        product = products.get(item["product_id"])
        if not product or product.get("stock", 0) < item["quantity"]:
            name = item["product_name"]
            raise OrderError(f"'{name}' no longer has enough stock available", 409)

    subtotal = cart["subtotal"]
    discount = 0.0  # placeholder -- points redemption will plug in here later
    delivery_fee = _delivery_fee(shipping_address)
    total = round(subtotal - discount + delivery_fee, 2)   # what the customer pays via M-Pesa
    points_earned = int((subtotal - discount) // KES_PER_POINT)   # points are on goods, not delivery

    order_insert = (
        supabase.table("orders")
        .insert(
            {
                "user_id": user_id,
                "status": "pending",
                "subtotal": subtotal,
                "discount": discount,
                "delivery_fee": delivery_fee,
                "total": total,
                "shipping_address": shipping_address.strip(),
                "points_earned": points_earned,
                "qr_token": secrets.token_urlsafe(12),  # printed as a QR on the package card
            }
        )
        .execute()
    )
    order = order_insert.data[0]

    order_items_payload = [
        {
            "order_id": order["id"],
            "product_id": item["product_id"],
            "size": item.get("size"),
            "color": item.get("color"),
            "quantity": item["quantity"],
            "price_at_purchase": item["price"],
        }
        for item in cart["items"]
    ]
    order_items_result = supabase.table("order_items").insert(order_items_payload).execute()

    # Reserve stock now; it is given back if payment fails (cancel_unpaid_order).
    for item in cart["items"]:
        product = products[item["product_id"]]
        new_stock = product["stock"] - item["quantity"]
        supabase.table("products").update({"stock": new_stock}).eq("id", product["id"]).execute()

    # Points are NOT credited here any more: the customer claims them by scanning
    # the QR card in the package (claim_order_qr). Cart clearing, the referral bonus
    # and badges now happen once M-Pesa confirms payment (complete_order_after_payment).

    items = [
        public_order_item(oi, products.get(oi["product_id"])) for oi in order_items_result.data
    ]
    return public_order(order, items)


def get_orders(user_id: str) -> list:
    supabase = get_supabase()
    result = (
        supabase.table("orders")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [public_order(o) for o in result.data]


def get_order_detail(user_id: str, order_id: str) -> dict:
    supabase = get_supabase()
    order_result = (
        supabase.table("orders").select("*").eq("id", order_id).eq("user_id", user_id).execute()
    )
    if not order_result.data:
        raise OrderError("Order not found", 404)
    order = order_result.data[0]

    items_result = supabase.table("order_items").select("*").eq("order_id", order_id).execute()
    product_ids = [oi["product_id"] for oi in items_result.data]
    products_result = (
        supabase.table("products").select("*").in_("id", product_ids).execute() if product_ids else None
    )
    products = {p["id"]: p for p in products_result.data} if products_result else {}

    items = [public_order_item(oi, products.get(oi["product_id"])) for oi in items_result.data]
    return public_order(order, items)


# ---------------------------------------------------------------
# Payment lifecycle (called from services/payment_service.py)
# ---------------------------------------------------------------
def complete_order_after_payment(order_id: str):
    """Runs once, right after M-Pesa confirms the order is paid."""
    supabase = get_supabase()
    result = supabase.table("orders").select("user_id").eq("id", order_id).execute()
    if not result.data:
        return
    user_id = result.data[0]["user_id"]
    supabase.table("cart_items").delete().eq("user_id", user_id).execute()
    _maybe_grant_referral_bonus(supabase, user_id)
    check_and_unlock_badges(user_id)


def cancel_unpaid_order(order_id: str):
    """Gives reserved stock back after a failed / cancelled / timed-out payment."""
    supabase = get_supabase()
    items = supabase.table("order_items").select("product_id, quantity").eq("order_id", order_id).execute().data
    if not items:
        return
    product_ids = [i["product_id"] for i in items]
    products = {
        p["id"]: p
        for p in supabase.table("products").select("id, stock").in_("id", product_ids).execute().data
    }
    for i in items:
        product = products.get(i["product_id"])
        if product:
            supabase.table("products").update(
                {"stock": product["stock"] + i["quantity"]}
            ).eq("id", product["id"]).execute()


# ---------------------------------------------------------------
# Scan-to-claim: customer scans the QR card inside the package
# ---------------------------------------------------------------
# Statuses that mean "the package is with the customer". Adjust to your real values.
CLAIMABLE_STATUSES = ("shipped", "delivered")


def claim_order_qr(user_id: str, code: str) -> dict:
    code = (code or "").strip()
    if not code:
        raise OrderError("Missing code")

    supabase = get_supabase()
    found = supabase.table("orders").select("*").eq("qr_token", code).execute()
    if not found.data:
        raise OrderError("This card is not valid", 404)
    order = found.data[0]

    if order.get("qr_claimed_at"):
        raise OrderError("This card has already been claimed")
    if order["status"] not in CLAIMABLE_STATUSES:
        raise OrderError("This order hasn't been shipped yet")

    # Atomic one-time claim: only one request can flip qr_claimed_at from null
    claimed = (
        supabase.table("orders")
        .update({"qr_claimed_at": datetime.now(timezone.utc).isoformat(), "qr_claimed_by": user_id})
        .eq("id", order["id"])
        .is_("qr_claimed_at", "null")
        .execute()
    )
    if not claimed.data:
        raise OrderError("This card has already been claimed")

    points = order.get("points_earned") or 0
    if points > 0:
        _credit_points(supabase, user_id, points, "earn", f"Order #{order['id'][:8]} (scanned)", order["id"])
        check_and_unlock_badges(user_id)

    balance = supabase.table("users").select("points_balance").eq("id", user_id).execute().data[0]["points_balance"]
    return {
        "message": f"+{points} points added!",
        "points_awarded": points,
        "points_balance": balance,
    }