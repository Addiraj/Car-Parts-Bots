from flask import Flask
from dotenv import load_dotenv
from .config import AppConfig
from .extensions import db, migrate, cors
from .routes import register_routes

def create_app(config: type[AppConfig] | None = None) -> Flask:
    # Load variables from a local .env if present (no-op if missing)
    load_dotenv()
    app = Flask(__name__)

    # Config
    app.config.from_object(config or AppConfig())

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/*": {"origins": "*"}})

    # Blueprints / Routes
    register_routes(app)

    return app


