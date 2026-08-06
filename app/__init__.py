from flask import Flask, g, redirect, url_for

from config import Config
from app.extensions import db, migrate
from app.auth_utils import load_logged_in_user


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401  (register models with SQLAlchemy metadata)

    from app.routes.auth import bp as auth_bp
    from app.routes.recipes import bp as recipes_bp
    from app.routes.ingest import bp as ingest_bp
    from app.routes.pantries import bp as pantries_bp
    from app.routes.grocery import bp as grocery_bp
    from app.routes.what_can_i_make import bp as what_can_i_make_bp
    from app.routes.equivalencies import bp as equivalencies_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(pantries_bp)
    app.register_blueprint(grocery_bp)
    app.register_blueprint(what_can_i_make_bp)
    app.register_blueprint(equivalencies_bp)

    app.before_request(load_logged_in_user)

    @app.route("/")
    def index():
        if g.user is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for("recipes.list_recipes"))

    return app
