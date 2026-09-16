from flask import Blueprint, request, jsonify, g
from services.wall_service import get_leaderboard, get_testimonials, submit_testimonial, get_pending_testimonials, moderate_testimonial, WallError
from utils.middleware import require_auth,require_admin

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
@wall_bp.route("/admin/testimonials/pending", methods=["GET"])
@require_admin
def pending_testimonials():
    return jsonify({"testimonials": get_pending_testimonials()}), 200


@wall_bp.route("/admin/testimonials/<testimonial_id>", methods=["PATCH"])
@require_admin
def review_testimonial(testimonial_id):
    data = request.get_json(silent=True) or {}
    try:
        result = moderate_testimonial(testimonial_id, bool(data.get("approve")))
        return jsonify(result), 200
    except WallError as e:
        return jsonify({"error": e.message}), e.status_code
