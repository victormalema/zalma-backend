from flask import Blueprint, request, jsonify, g
from services.cart_service import (
    get_cart,
    add_to_cart,
    update_cart_item,
    remove_cart_item,
    CartError,
)
from utils.middleware import require_auth

cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")


@cart_bp.route("", methods=["GET"])
@require_auth
def view_cart():
    return jsonify(get_cart(g.user_id)), 200


@cart_bp.route("", methods=["POST"])
@require_auth
def add_item():
    data = request.get_json(silent=True) or {}
    try:
        item = add_to_cart(
            user_id=g.user_id,
            product_id=data.get("product_id"),
            size=data.get("size"),
            color=data.get("color"),
            quantity=int(data.get("quantity", 1)),
        )
        return jsonify({"item": item}), 201
    except CartError as e:
        return jsonify({"error": e.message}), e.status_code


@cart_bp.route("/<item_id>", methods=["PATCH"])
@require_auth
def update_item(item_id):
    data = request.get_json(silent=True) or {}
    try:
        result = update_cart_item(g.user_id, item_id, int(data.get("quantity", 1)))
        return jsonify(result), 200
    except CartError as e:
        return jsonify({"error": e.message}), e.status_code


@cart_bp.route("/<item_id>", methods=["DELETE"])
@require_auth
def delete_item(item_id):
    try:
        remove_cart_item(g.user_id, item_id)
        return jsonify({"deleted": True}), 200
    except CartError as e:
        return jsonify({"error": e.message}), e.status_code
