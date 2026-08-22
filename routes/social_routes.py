from flask import Blueprint, request, jsonify, g
from services.social_service import claim_follow, get_claimed_platforms, SocialError
from utils.middleware import require_auth

social_bp = Blueprint("social", __name__, url_prefix="/api/social")


@social_bp.route("/follow", methods=["GET"])
@require_auth
def list_follows():
    return jsonify({"claimed": get_claimed_platforms(g.user_id)}), 200


@social_bp.route("/follow", methods=["POST"])
@require_auth
def follow():
    data = request.get_json(silent=True) or {}
    try:
        result = claim_follow(g.user_id, data.get("platform"))
        return jsonify(result), 201
    except SocialError as e:
        return jsonify({"error": e.message}), e.status_code
