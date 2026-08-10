from flask import Blueprint, jsonify, g
from services.badges_service import get_user_badges, check_and_unlock_badges
from utils.middleware import require_auth

badges_bp = Blueprint("badges", __name__, url_prefix="/api/badges")


@badges_bp.route("", methods=["GET"])
@require_auth
def view_badges():
    check_and_unlock_badges(g.user_id)
    return jsonify({"badges": get_user_badges(g.user_id)}), 200
