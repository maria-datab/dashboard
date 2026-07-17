from routes.core import bp as core_bp


def register_blueprints(app):
    """Register tier-0 route blueprints."""
    app.register_blueprint(core_bp)
