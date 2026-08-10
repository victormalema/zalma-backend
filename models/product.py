def public_collection(collection: dict) -> dict:
    return {
        "id": collection["id"],
        "name": collection["name"],
        "slug": collection["slug"],
        "description": collection.get("description"),
        "cover_image": collection.get("cover_image"),
    }


def public_product(product: dict, collection: dict = None) -> dict:
    result = {
        "id": product["id"],
        "name": product["name"],
        "slug": product["slug"],
        "price": float(product["price"]),
        "description": product.get("description"),
        "sizes": product.get("sizes", []),
        "colors": product.get("colors", []),
        "images": product.get("images", []),
        "stock": product.get("stock", 0),
        "in_stock": product.get("stock", 0) > 0,
        "collection_id": product.get("collection_id"),
    }
    if collection:
        result["collection"] = {
            "name": collection.get("name"),
            "slug": collection.get("slug"),
        }
    return result
