from flask import Blueprint, current_app, jsonify, request

from backend.services.analysis_service import analyze_product_image


api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.post("/analyze")
def analyze():
    image = request.files.get("image")
    if image is None or image.filename == "":
        return jsonify({"error": "Image file is required in form field 'image'."}), 400

    if not _is_allowed_image(image.mimetype, image.filename):
        return jsonify({"error": "Only JPG, JPEG, PNG, and WEBP images are supported."}), 400

    image_bytes = image.read()
    knowledge_base = current_app.config["KNOWLEDGE_BASE"]
    result = analyze_product_image(image_bytes, knowledge_base)
    return jsonify(result)


def _is_allowed_image(mimetype, filename):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    allowed_mimetypes = {"image/jpeg", "image/png", "image/webp"}
    lower_name = filename.lower()
    return (
        any(lower_name.endswith(ext) for ext in allowed_extensions)
        and mimetype in allowed_mimetypes
    )
