from flask import Blueprint, request, jsonify, g
from services.orders_service import checkout, get_orders, get_order_detail, OrderError
from utils.middleware import require_auth

orders_bp = Blueprint("orders", __name__, url_prefix="/api")


@orders_bp.route("/checkout", methods=["POST"])
@require_auth
def do_checkout():
    data = request.get_json(silent=True) or {}
    try:
        order = checkout(g.user_id, data.get("shipping_address"))
        return jsonify({"order": order}), 201
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code


@orders_bp.route("/orders", methods=["GET"])
@require_auth
def list_orders():
    return jsonify({"orders": get_orders(g.user_id)}), 200


@orders_bp.route("/orders/<order_id>", methods=["GET"])
@require_auth
def order_detail(order_id):
    try:
        order = get_order_detail(g.user_id, order_id)
        return jsonify({"order": order}), 200
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code
