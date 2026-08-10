from flask import Blueprint, request, jsonify, g
from services.rewards_service import get_rewards_summary, redeem_points, RewardsError
from utils.middleware import require_auth

rewards_bp = Blueprint("rewards", __name__, url_prefix="/api/rewards")


@rewards_bp.route("", methods=["GET"])
@require_auth
def view_rewards():
    try:
        return jsonify(get_rewards_summary(g.user_id)), 200
    except RewardsError as e:
        return jsonify({"error": e.message}), e.status_code


@rewards_bp.route("/redeem", methods=["POST"])
@require_auth
def redeem():
    data = request.get_json(silent=True) or {}
    try:
        points = int(data.get("points", 0))
        result = redeem_points(g.user_id, points)
        return jsonify(result), 200
    except (ValueError, TypeError):
        return jsonify({"error": "points must be a number"}), 400
    except RewardsError as e:
        return jsonify({"error": e.message}), e.status_code
