from flask import Blueprint, request, jsonify, g
from services.wishlist_service import (
    get_wishlist,
    add_to_wishlist,
    remove_from_wishlist,
    WishlistError,
)
from utils.middleware import require_auth

wishlist_bp = Blueprint("wishlist", __name__, url_prefix="/api/wishlist")


@wishlist_bp.route("", methods=["GET"])
@require_auth
def view_wishlist():
    return jsonify({"items": get_wishlist(g.user_id)}), 200


@wishlist_bp.route("", methods=["POST"])
@require_auth
def add_item():
    data = request.get_json(silent=True) or {}
    try:
        item = add_to_wishlist(g.user_id, data.get("product_id"))
        return jsonify({"item": item}), 201
    except WishlistError as e:
        return jsonify({"error": e.message}), e.status_code


@wishlist_bp.route("/<product_id>", methods=["DELETE"])
@require_auth
def delete_item(product_id):
    remove_from_wishlist(g.user_id, product_id)
    return jsonify({"deleted": True}), 200
