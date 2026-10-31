from flask import Blueprint, request, jsonify
from services.admin_service import (
    get_dashboard_stats,
    get_all_users,
    get_all_orders,
    update_order_status,
    AdminError,
)
from services.fulfilment_service import FulfilmentError, check_status_change, get_order_qr
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
    new_status = data.get("status")
    try:
        check_status_change(order_id, new_status)      # blocks e.g. pending -> shipped
        result = update_order_status(order_id, new_status)
        return jsonify(result), 200
    except FulfilmentError as e:
        return jsonify({"error": e.message}), e.status_code
    except AdminError as e:
        return jsonify({"error": e.message}), e.status_code


# Data for the printable QR card that goes inside the package
@admin_bp.route("/orders/<order_id>/qr", methods=["GET"])
@require_admin
def order_qr(order_id):
    try:
        return jsonify(get_order_qr(order_id)), 200
    except FulfilmentError as e:
        return jsonify({"error": e.message}), e.status_code