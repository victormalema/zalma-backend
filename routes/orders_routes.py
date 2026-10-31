"""
routes/orders_routes.py  (REBUILT -- only needed if you could not restore the original from git)

Paths match api.js:  POST /api/checkout, GET /api/orders, GET /api/orders/<id>
Response shape matches checkout.html:  {"order": {...}}
"""
from flask import Blueprint, request, jsonify, g

from services.orders_service import OrderError, checkout, get_order_detail, get_orders
from utils.middleware import require_auth

orders_bp = Blueprint("orders", __name__)


# POST /api/checkout  { "shipping_address": "..." }  -> creates a PENDING order.
# The customer then pays with POST /api/payments/pay.
@orders_bp.route("/api/checkout", methods=["POST"])
@require_auth
def place_order():
    data = request.get_json(silent=True) or {}
    try:
        order = checkout(g.user_id, data.get("shipping_address"))
        return jsonify({"order": order}), 201
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code


# GET /api/orders
@orders_bp.route("/api/orders", methods=["GET"])
@require_auth
def list_orders():
    return jsonify({"orders": get_orders(g.user_id)}), 200


# GET /api/orders/<order_id>
@orders_bp.route("/api/orders/<order_id>", methods=["GET"])
@require_auth
def order_detail(order_id):
    try:
        return jsonify({"order": get_order_detail(g.user_id, order_id)}), 200
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code