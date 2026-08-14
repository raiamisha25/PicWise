from flask import Flask, render_template

from backend.routes.api import api_bp
from backend.services.knowledge_base import KnowledgeBase


def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config["KNOWLEDGE_BASE"] = KnowledgeBase.from_env()

    app.register_blueprint(api_bp)

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/upload")
    def upload():
        return render_template("upload.html")

    return app
