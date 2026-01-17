"""GitLab Deployer Flask Application"""
from flask import Flask

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

    from . import routes
    app.register_blueprint(routes.bp)

    return app
