from flask import Blueprint, jsonify, g
from services.tiers_service import get_rank_status
from utils.middleware import require_auth

tiers_bp = Blueprint("tiers", __name__, url_prefix="/api/rank")


@tiers_bp.route("", methods=["GET"])
@require_auth
def rank_status():
    return jsonify(get_rank_status(g.user_id)), 200
