"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify, url_for, send_from_directory
from flask_migrate import Migrate
from flask_swagger import swagger
from api.utils import APIException, generate_sitemap
from flask_jwt_extended import JWTManager
from api.models import db
from api.routes import api
from api.promotor import promotor
from api.user import api as user
from api.admins import admins
from api.category import category
from api.event import event
from api.group import group
from api.admin import setup_admin
from api.commands import setup_commands
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from api.socket_events import register_socket_events
from api.image_search import image_search
# from models import Person

ENV = "development" if os.getenv("FLASK_DEBUG") == "1" else "production"
static_file_dir = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), '../dist/')
app = Flask(__name__)
app.url_map.strict_slashes = False

# In development the Vite preview can run on a changing Codespaces origin.
# Production accepts only origins explicitly configured in CORS_ORIGINS.
configured_origins = os.getenv("CORS_ORIGINS", "").strip()
if configured_origins:
    allowed_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
elif ENV == "development":
    allowed_origins = "*"
else:
    allowed_origins = None

socketio = SocketIO(app, cors_allowed_origins=allowed_origins)
register_socket_events(socketio)
if allowed_origins is not None:
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}},
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=False)

# database condiguration
db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace(
        "postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
MIGRATE = Migrate(app, db, compare_type=True)
db.init_app(app)

with app.app_context():
    if ENV == "development":
        db.create_all()
# add the admin
if os.getenv("ENABLE_FLASK_ADMIN") == "1":
    setup_admin(app)

# add the admin
setup_commands(app)

# Add all endpoints form the API with a "api" prefix
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(promotor, url_prefix='/api/promotor')
app.register_blueprint(group, url_prefix='/api')
app.register_blueprint(admins, url_prefix='/api')
app.register_blueprint(event, url_prefix='/api')
app.register_blueprint(category, url_prefix='/api')
app.register_blueprint(user, url_prefix='/api')
app.register_blueprint(image_search, url_prefix="/api")

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
if not app.config["JWT_SECRET_KEY"]:
    if ENV == "production":
        raise RuntimeError("JWT_SECRET_KEY debe configurarse en producción")
    app.config["JWT_SECRET_KEY"] = "development-only-change-me-please-replace-with-real-secret"
jwt = JWTManager(app)

# Handle/serialize errors like a JSON object


@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints


@app.route('/')
def sitemap():
    if ENV == "development":
        return generate_sitemap(app)
    return send_from_directory(static_file_dir, 'index.html')

# any other endpoint will try to serve it like a static file


@app.route('/<path:path>', methods=['GET'])
def serve_any_other_file(path):
    if not os.path.isfile(os.path.join(static_file_dir, path)):
        path = 'index.html'
    response = send_from_directory(static_file_dir, path)
    response.cache_control.max_age = 0  # avoid cache memory
    return response


# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3001))
    socketio.run(app, host='0.0.0.0', port=PORT, debug=True)
