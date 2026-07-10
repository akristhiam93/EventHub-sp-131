from flask import request, jsonify, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, verify_jwt_in_request
from sqlalchemy import select
from api.models import db, Admin
from api.security import current_account_id, current_role, hash_password, issue_token, verify_password


admins = Blueprint('admins', __name__)


@admins.before_request
def require_admin_role():
    if request.method == "OPTIONS":
        return None
    if request.endpoint == "admins.login_admin":
        return None
    verify_jwt_in_request()
    if current_role() != "admin":
        return jsonify({"message": "Se requiere rol de administrador"}), 403


@admins.route('/admin/login', methods=['POST'])
def login_admin():
    body = request.get_json()

    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        return jsonify({"msg": "Email y password requeridos"}), 400

    admin = db.session.execute(
        select(Admin).where(Admin.email == email)
    ).scalar_one_or_none()

    if not admin:
        return jsonify({"msg": "Credenciales inválidas"}), 401

    if not verify_password(admin.password, password):
        return jsonify({"msg": "Credenciales inválidas"}), 401

    if not admin.password.startswith(("pbkdf2:", "scrypt:")):
        admin.password = hash_password(password)
        db.session.commit()
    token = issue_token(admin, "admin")

    return jsonify({
        "token": token,
        "admin": admin.serialize()
    }), 200


@admins.route('/admin/private', methods=['GET'])
@jwt_required()
def private_admin():
    if current_role() != "admin":
        return jsonify({"msg": "No tienes permisos para esta ruta"}), 403
    admin = db.session.get(Admin, current_account_id())

    if not admin:
        return jsonify({"msg": "Admin no encontrado"}), 404

    return jsonify({
        "msg": "Token válido",
        "admin": admin.serialize()
    }), 200


@admins.route('/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Bien"}), 200
