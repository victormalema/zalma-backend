def public_order_item(item: dict, product: dict = None) -> dict:
    price = float(item["price_at_purchase"])
    quantity = item["quantity"]
    return {
        "id": item["id"],
        "product_id": item["product_id"],
        "product_name": product["name"] if product else None,
        "product_image": (product.get("images") or [None])[0] if product else None,
        "size": item.get("size"),
        "color": item.get("color"),
        "quantity": quantity,
        "price_at_purchase": price,
        "subtotal": round(price * quantity, 2),
    }


def public_order(order: dict, items: list = None) -> dict:
    result = {
        "id": order["id"],
        "status": order["status"],
        "subtotal": float(order["subtotal"]),
        "discount": float(order["discount"]),
        "total": float(order["total"]),
        "shipping_address": order["shipping_address"],
        "points_earned": order["points_earned"],
        "created_at": order["created_at"],
    }
    if items is not None:
        result["items"] = items
    return result
