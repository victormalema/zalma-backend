from flask import Blueprint, request, jsonify, g
from services.wall_service import get_leaderboard, get_testimonials, submit_testimonial, WallError
from utils.middleware import require_auth

wall_bp = Blueprint("wall", __name__, url_prefix="/api/wall")


@wall_bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify({"leaderboard": get_leaderboard()}), 200


@wall_bp.route("/testimonials", methods=["GET"])
def testimonials():
    return jsonify({"testimonials": get_testimonials()}), 200


@wall_bp.route("/testimonials", methods=["POST"])
@require_auth
def submit():
    data = request.get_json(silent=True) or {}
    try:
        result = submit_testimonial(g.user_id, data.get("content"), data.get("image"))
        return jsonify(result), 201
    except WallError as e:
        return jsonify({"error": e.message}), e.status_code
