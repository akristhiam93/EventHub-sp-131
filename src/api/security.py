"""Shared authentication and authorization helpers."""
from functools import wraps

from flask import jsonify
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password):
    return generate_password_hash(password)


def verify_password(stored_password, candidate):
    """Accept legacy plaintext only until it is upgraded at the next login."""
    if not stored_password:
        return False
    if stored_password.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored_password, candidate)
    return stored_password == candidate


def issue_token(account, role):
    return create_access_token(identity=str(account.id), additional_claims={"role": role})


def current_role():
    return get_jwt().get("role")


def current_account_id():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            if current_role() not in roles:
                return jsonify({"message": "No tienes permisos para esta acción"}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator
