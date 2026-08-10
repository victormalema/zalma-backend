from flask import Blueprint, request, jsonify, g
from services.auth_service import signup_user, login_user, get_user_profile, AuthError
from utils.middleware import require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    try:
        token, user = signup_user(
            email=data.get("email"),
            password=data.get("password"),
            name=data.get("name"),
            phone=data.get("phone"),
            referral_code=data.get("referral_code"),
        )
        return jsonify({"token": token, "user": user}), 201
    except AuthError as e:
        return jsonify({"error": e.message}), e.status_code


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    try:
        token, user = login_user(
            email=data.get("email"),
            password=data.get("password"),
        )
        return jsonify({"token": token, "user": user}), 200
    except AuthError as e:
        return jsonify({"error": e.message}), e.status_code


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    try:
        user = get_user_profile(g.user_id)
        return jsonify({"user": user}), 200
    except AuthError as e:
        return jsonify({"error": e.message}), e.status_code
