from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt
from .routes.api import api_bp
from .routes.auth import auth_bp


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    db.init_app(app)
    jwt.init_app(app)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "skillbridge-flask"}

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(success=False, error="Resource not found."), 404

    return app
