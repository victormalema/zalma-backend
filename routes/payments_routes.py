"""
routes/payments_routes.py
M-Pesa payment endpoints + scan-to-claim endpoint.

Env vars used (besides the MPESA_* ones from mpesa_service.py):
  MPESA_CALLBACK_SECRET   random string that is part of the callback URL
"""
import hmac
import logging
import os

from flask import Blueprint, request, jsonify, g

from services.mpesa_service import MpesaError
from services.cleanup_service import release_abandoned_orders
from services.orders_service import OrderError, claim_order_qr, delivery_fee_config
from services.payment_service import get_payment_status, handle_callback, initiate_payment
from utils.middleware import require_auth

log = logging.getLogger(__name__)

payments_bp = Blueprint("payments", __name__, url_prefix="/api")


# ---------------------------------------------------------------
# Public: current delivery pricing, so the checkout page always matches the server
# GET /api/delivery-fees
# ---------------------------------------------------------------
@payments_bp.route("/delivery-fees", methods=["GET"])
def delivery_fees():
    return jsonify(delivery_fee_config()), 200


# ---------------------------------------------------------------
# Customer starts a payment for a pending order
# POST /api/payments/pay    { "order_id": "...", "phone": "0712345678" }
# ---------------------------------------------------------------
@payments_bp.route("/payments/pay", methods=["POST"])
@require_auth
def pay():
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    phone = data.get("phone")
    if not order_id or not phone:
        return jsonify({"error": "order_id and phone are required"}), 400
    try:
        return jsonify(initiate_payment(g.user_id, order_id, phone)), 200
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code
    except MpesaError as e:
        return jsonify({"error": e.message}), e.status_code


# ---------------------------------------------------------------
# Safaricom calls this when the customer pays / cancels / times out.
# No login here -- protected by the secret in the URL instead.
# ---------------------------------------------------------------
@payments_bp.route("/payments/callback/<secret>", methods=["POST"])
def payment_callback(secret):
    expected = os.environ.get("MPESA_CALLBACK_SECRET", "")
    if not expected or not hmac.compare_digest(secret, expected):
        return jsonify({"error": "Forbidden"}), 403

    body = request.get_json(silent=True) or {}
    try:
        handle_callback(body)
    except Exception:
        # Never let an error bubble back to Safaricom; log it so you can investigate.
        log.exception("Failed to process M-Pesa callback")
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200


# ---------------------------------------------------------------
# Optional: an outside timer (e.g. cron-job.org, every 15 min) can call this to
# release stock from abandoned orders even when nobody is using the site.
# Disabled unless CRON_SECRET is set on the server.
# ---------------------------------------------------------------
@payments_bp.route("/payments/cleanup/<secret>", methods=["GET", "POST"])
def cleanup(secret):
    expected = os.environ.get("CRON_SECRET", "")
    if not expected or not hmac.compare_digest(secret, expected):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(release_abandoned_orders()), 200
    except Exception:
        log.exception("Cleanup run failed")
        return jsonify({"error": "Cleanup failed"}), 500


# ---------------------------------------------------------------
# Checkout page polls this while the customer enters their PIN
# GET /api/orders/<order_id>/payment-status
# ---------------------------------------------------------------
@payments_bp.route("/orders/<order_id>/payment-status", methods=["GET"])
@require_auth
def payment_status(order_id):
    try:
        return jsonify(get_payment_status(g.user_id, order_id)), 200
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code


# ---------------------------------------------------------------
# Customer scans the QR card in the package
# POST /api/orders/claim-qr    { "code": "..." }
# ---------------------------------------------------------------
@payments_bp.route("/orders/claim-qr", methods=["POST"])
@require_auth
def claim_qr():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(claim_order_qr(g.user_id, data.get("code"))), 200
    except OrderError as e:
        return jsonify({"error": e.message}), e.status_code