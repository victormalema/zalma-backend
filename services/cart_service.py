from database.supabase_client import get_supabase
from models.cart import public_cart_item


class CartError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _products_by_id(supabase, product_ids: list) -> dict:
    if not product_ids:
        return {}
    result = supabase.table("products").select("*").in_("id", product_ids).execute()
    return {p["id"]: p for p in result.data}


def get_cart(user_id: str) -> dict:
    supabase = get_supabase()
    items_result = supabase.table("cart_items").select("*").eq("user_id", user_id).execute()
    items = items_result.data

    products = _products_by_id(supabase, [i["product_id"] for i in items])

    cart_items = []
    for item in items:
        product = products.get(item["product_id"])
        if product:
            cart_items.append(public_cart_item(item, product))

    subtotal = round(sum(ci["subtotal"] for ci in cart_items), 2)
    return {"items": cart_items, "subtotal": subtotal, "count": len(cart_items)}


def add_to_cart(user_id: str, product_id: str, size: str = None,
                 color: str = None, quantity: int = 1) -> dict:
    if quantity < 1:
        raise CartError("quantity must be at least 1")

    supabase = get_supabase()

    product_result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not product_result.data:
        raise CartError("Product not found", 404)
    product = product_result.data[0]

    query = (
        supabase.table("cart_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("product_id", product_id)
    )
    query = query.is_("size", "null") if size is None else query.eq("size", size)
    query = query.is_("color", "null") if color is None else query.eq("color", color)
    existing = query.execute()

    if existing.data:
        item = existing.data[0]
        new_quantity = item["quantity"] + quantity
        if new_quantity > product.get("stock", 0):
            raise CartError(f"Only {product.get('stock', 0)} left in stock", 409)
        update_result = (
            supabase.table("cart_items")
            .update({"quantity": new_quantity})
            .eq("id", item["id"])
            .execute()
        )
        return public_cart_item(update_result.data[0], product)

    if quantity > product.get("stock", 0):
        raise CartError(f"Only {product.get('stock', 0)} left in stock", 409)

    insert_result = (
        supabase.table("cart_items")
        .insert(
            {
                "user_id": user_id,
                "product_id": product_id,
                "size": size,
                "color": color,
                "quantity": quantity,
            }
        )
        .execute()
    )
    return public_cart_item(insert_result.data[0], product)


def update_cart_item(user_id: str, item_id: str, quantity: int) -> dict:
    supabase = get_supabase()

    existing = (
        supabase.table("cart_items")
        .select("*")
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not existing.data:
        raise CartError("Cart item not found", 404)

    if quantity < 1:
        supabase.table("cart_items").delete().eq("id", item_id).execute()
        return {"deleted": True}

    product_result = (
        supabase.table("products").select("*").eq("id", existing.data[0]["product_id"]).execute()
    )
    product = product_result.data[0]
    if quantity > product.get("stock", 0):
        raise CartError(f"Only {product.get('stock', 0)} left in stock", 409)

    update_result = (
        supabase.table("cart_items").update({"quantity": quantity}).eq("id", item_id).execute()
    )
    return public_cart_item(update_result.data[0], product)


def remove_cart_item(user_id: str, item_id: str) -> None:
    supabase = get_supabase()
    existing = (
        supabase.table("cart_items")
        .select("id")
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not existing.data:
        raise CartError("Cart item not found", 404)
    supabase.table("cart_items").delete().eq("id", item_id).execute()
