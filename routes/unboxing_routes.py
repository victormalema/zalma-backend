from flask import Blueprint, request, jsonify, g
from services.unboxing_service import submit_unboxing, get_user_unboxings, UnboxingError
from utils.middleware import require_auth

unboxing_bp = Blueprint("unboxing", __name__, url_prefix="/api/unboxing")


@unboxing_bp.route("", methods=["GET"])
@require_auth
def list_unboxings():
    return jsonify({"submissions": get_user_unboxings(g.user_id)}), 200


@unboxing_bp.route("", methods=["POST"])
@require_auth
def submit():
    data = request.get_json(silent=True) or {}
    try:
        result = submit_unboxing(g.user_id, data.get("video_url"))
        return jsonify(result), 201
    except UnboxingError as e:
        return jsonify({"error": e.message}), e.status_code
