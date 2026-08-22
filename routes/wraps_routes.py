from flask import Blueprint, jsonify, g
from services.wraps_service import get_user_wraps
from utils.middleware import require_auth

wraps_bp = Blueprint("wraps", __name__, url_prefix="/api/wraps")


@wraps_bp.route("", methods=["GET"])
@require_auth
def list_wraps():
    return jsonify({"wraps": get_user_wraps(g.user_id)}), 200

