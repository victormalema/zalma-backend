def public_preorder_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item.get("description"),
        "price": item["price"],
        "image": item.get("image_url"),
        "sizes": item.get("sizes") or [],
        "colors": item.get("colors") or [],
        "lot_label": item.get("lot_label") or "Lot 02",
        "closes_at": item.get("closes_at"),
    }


def public_preorder(row: dict, item: dict = None) -> dict:
    return {
        "id": row["id"],
        "status": row["status"],
        "size": row.get("size"),
        "color": row.get("color"),
        "quantity": row["quantity"],
        "phone": row["phone"],
        "created_at": row.get("created_at"),
        "item": public_preorder_item(item) if item else None,
    }
