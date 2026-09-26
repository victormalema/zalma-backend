from flask import Blueprint, request, jsonify
from services.admin_service import (
    get_dashboard_stats,
    get_all_users,
    get_all_orders,
    update_order_status,
    AdminError,
)
from utils.middleware import require_admin

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/dashboard", methods=["GET"])
@require_admin
def dashboard():
    return jsonify(get_dashboard_stats()), 200


@admin_bp.route("/users", methods=["GET"])
@require_admin
def users():
    return jsonify({"users": get_all_users()}), 200


@admin_bp.route("/orders", methods=["GET"])
@require_admin
def orders():
    return jsonify({"orders": get_all_orders()}), 200


@admin_bp.route("/orders/<order_id>", methods=["PATCH"])
@require_admin
def update_order(order_id):
    data = request.get_json(silent=True) or {}
    try:
        result = update_order_status(order_id, data.get("status"))
        return jsonify(result), 200
    except AdminError as e:
        return jsonify({"error": e.message}), e.status_code
