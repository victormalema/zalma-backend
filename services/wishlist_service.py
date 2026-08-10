from database.supabase_client import get_supabase
from models.cart import public_wishlist_item


class WishlistError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_wishlist(user_id: str) -> list:
    supabase = get_supabase()
    items_result = supabase.table("wishlist_items").select("*").eq("user_id", user_id).execute()
    items = items_result.data

    if not items:
        return []

    product_ids = [i["product_id"] for i in items]
    products_result = supabase.table("products").select("*").in_("id", product_ids).execute()
    products = {p["id"]: p for p in products_result.data}

    return [
        public_wishlist_item(item, products[item["product_id"]])
        for item in items
        if item["product_id"] in products
    ]


def add_to_wishlist(user_id: str, product_id: str) -> dict:
    supabase = get_supabase()

    product_result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not product_result.data:
        raise WishlistError("Product not found", 404)
    product = product_result.data[0]

    existing = (
        supabase.table("wishlist_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("product_id", product_id)
        .execute()
    )
    if existing.data:
        return public_wishlist_item(existing.data[0], product)

    insert_result = (
        supabase.table("wishlist_items")
        .insert({"user_id": user_id, "product_id": product_id})
        .execute()
    )
    return public_wishlist_item(insert_result.data[0], product)


def remove_from_wishlist(user_id: str, product_id: str) -> None:
    supabase = get_supabase()
    supabase.table("wishlist_items").delete().eq("user_id", user_id).eq(
        "product_id", product_id
    ).execute()
