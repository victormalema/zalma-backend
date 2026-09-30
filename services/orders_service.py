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
    orders_result = supabase.table("orders").select("id").eq("user_id", user_id).execute()
    if len(orders_result.data) != 1:
        return  # not their first order

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
    total = round(subtotal - discount, 2)
    points_earned = int(total // KES_PER_POINT)

    order_insert = (
        supabase.table("orders")
        .insert(
            {
                "user_id": user_id,
                "status": "pending",
                "subtotal": subtotal,
                "discount": discount,
                "total": total,
                "shipping_address": shipping_address.strip(),
                "points_earned": points_earned,
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

    # Decrement stock for each product ordered.
    for item in cart["items"]:
        product = products[item["product_id"]]
        new_stock = product["stock"] - item["quantity"]
        supabase.table("products").update({"stock": new_stock}).eq("id", product["id"]).execute()

    if points_earned > 0:
        _credit_points(
            supabase, user_id, points_earned, "earn", f"Order #{order['id'][:8]}", order["id"]
        )

    supabase.table("cart_items").delete().eq("user_id", user_id).execute()

    _maybe_grant_referral_bonus(supabase, user_id)
    check_and_unlock_badges(user_id)

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
