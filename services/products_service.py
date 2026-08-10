from database.supabase_client import get_supabase
from models.product import public_collection, public_product


class ProductError(Exception):
    """Raised for expected failures (not found, bad filter)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_all_collections() -> list:
    supabase = get_supabase()
    result = supabase.table("collections").select("*").order("created_at").execute()
    return [public_collection(c) for c in result.data]


def get_products(collection_slug: str = None) -> list:
    supabase = get_supabase()

    query = supabase.table("products").select("*").eq("is_active", True)

    if collection_slug:
        collection_result = (
            supabase.table("collections")
            .select("id")
            .eq("slug", collection_slug)
            .execute()
        )
        if not collection_result.data:
            raise ProductError(f"No collection found with slug '{collection_slug}'", 404)
        query = query.eq("collection_id", collection_result.data[0]["id"])

    result = query.order("created_at", desc=True).execute()
    return [public_product(p) for p in result.data]


def get_product_by_slug(slug: str) -> dict:
    supabase = get_supabase()

    result = (
        supabase.table("products")
        .select("*")
        .eq("slug", slug)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        raise ProductError("Product not found", 404)

    product = result.data[0]

    collection = None
    if product.get("collection_id"):
        collection_result = (
            supabase.table("collections")
            .select("name, slug")
            .eq("id", product["collection_id"])
            .execute()
        )
        if collection_result.data:
            collection = collection_result.data[0]

    return public_product(product, collection)
