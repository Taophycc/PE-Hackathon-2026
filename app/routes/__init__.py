def register_routes(app):
    from app.routes.links import links_bp
    app.register_blueprint(links_bp)
