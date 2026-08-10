def public_cart_item(item: dict, product: dict) -> dict:
    quantity = item["quantity"]
    price = float(product["price"])
    return {
        "id": item["id"],
        "product_id": item["product_id"],
        "product_name": product["name"],
        "product_slug": product["slug"],
        "product_image": (product.get("images") or [None])[0],
        "price": price,
        "size": item.get("size"),
        "color": item.get("color"),
        "quantity": quantity,
        "subtotal": round(price * quantity, 2),
        "in_stock": product.get("stock", 0) >= quantity,
    }


def public_wishlist_item(item: dict, product: dict) -> dict:
    return {
        "id": item["id"],
        "product_id": item["product_id"],
        "product_name": product["name"],
        "product_slug": product["slug"],
        "product_image": (product.get("images") or [None])[0],
        "price": float(product["price"]),
        "in_stock": product.get("stock", 0) > 0,
    }
