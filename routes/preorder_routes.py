from flask import Blueprint, request, jsonify, g
from services.preorder_service import (
    get_open_items,
    get_my_preorders,
    create_preorder,
    cancel_preorder,
    PreorderError,
)
from utils.middleware import require_auth

preorder_bp = Blueprint("preorder", __name__, url_prefix="/api/preorders")


@preorder_bp.route("/items", methods=["GET"])
def list_items():
    """Public: the pieces currently open for pre-order."""
    return jsonify({"items": get_open_items()}), 200


@preorder_bp.route("", methods=["GET"])
@require_auth
def my_preorders():
    return jsonify({"items": get_my_preorders(g.user_id)}), 200


@preorder_bp.route("", methods=["POST"])
@require_auth
def reserve():
    data = request.get_json(silent=True) or {}
    try:
        preorder = create_preorder(g.user_id, data)
        return jsonify({"preorder": preorder, "message": "Pre-order reserved"}), 201
    except PreorderError as e:
        return jsonify({"error": e.message}), e.status_code


@preorder_bp.route("/<preorder_id>", methods=["DELETE"])
@require_auth
def cancel(preorder_id):
    try:
        cancel_preorder(g.user_id, preorder_id)
        return jsonify({"cancelled": True}), 200
    except PreorderError as e:
        return jsonify({"error": e.message}), e.status_code
