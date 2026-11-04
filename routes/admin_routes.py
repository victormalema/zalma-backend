from flask import Blueprint, request, jsonify
from services.admin_service import (
    get_dashboard_stats,
    get_all_users,
    get_all_orders,
    update_order_status,
    get_all_preorders,
    update_preorder_status,
    set_preorder_item_active,
    AdminError,
)
from services.cleanup_service import run_cleanup_if_due
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
    run_cleanup_if_due()   # releases stock from abandoned unpaid orders (throttled, never raises)
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


# ---------- pre-orders ----------

@admin_bp.route("/preorders", methods=["GET"])
@require_admin
def preorders():
    return jsonify(get_all_preorders()), 200


@admin_bp.route("/preorders/<preorder_id>", methods=["PATCH"])
@require_admin
def update_preorder(preorder_id):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(update_preorder_status(preorder_id, data.get("status"))), 200
    except AdminError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/preorder-items/<item_id>", methods=["PATCH"])
@require_admin
def update_preorder_item(item_id):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(set_preorder_item_active(item_id, data.get("is_active"))), 200
    except AdminError as e:
        return jsonify({"error": e.message}), e.status_code