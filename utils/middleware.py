from functools import wraps
from flask import request, jsonify, g
from utils.security import decode_token
from database.supabase_client import get_supabase


def require_auth(f):
    """
    Reads the 'Authorization: Bearer <token>' header, validates the JWT,
    and sets g.user_id for the route to use. Returns 401 if missing/invalid.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        user_id = decode_token(token)

        if not user_id:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.user_id = user_id
        return f(*args, **kwargs)

    return wrapper


def require_admin(f):
    """
    Full auth check (same as require_auth) PLUS an admin check.
    Self-contained -- does not depend on require_auth having run first,
    so it's safe to use on its own without stacking decorators.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        user_id = decode_token(token)

        if not user_id:
            return jsonify({"error": "Invalid or expired token"}), 401

        supabase = get_supabase()
        result = supabase.table("users").select("is_admin").eq("id", user_id).execute()

        if not result.data or not result.data[0].get("is_admin"):
            return jsonify({"error": "Admin access required"}), 403

        g.user_id = user_id
        return f(*args, **kwargs)

    return wrapper
