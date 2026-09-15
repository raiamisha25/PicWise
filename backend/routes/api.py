import io
from flask import Blueprint, current_app, jsonify, request
from PIL import Image

from backend.services.analysis_service import analyze_product_image

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.post("/analyze")
def analyze():
    category = request.form.get("category")
    if not category or not category.strip():
        return jsonify({"error": "Product category is required in form field 'category'."}), 400

    category = category.strip().lower()
    if category not in ("food", "personal_care"):
        return jsonify({
            "error": f"Invalid category '{category}'. Allowed values are 'food' or 'personal_care'."
        }), 400

    image = request.files.get("image")
    if image is None or image.filename == "":
        return jsonify({"error": "Image file is required in form field 'image'."}), 400

    if not _is_allowed_image(image.mimetype, image.filename):
        return jsonify({"error": "Only JPG, JPEG, PNG, and WEBP images are supported."}), 400

    image_bytes = image.read()
    if not image_bytes or len(image_bytes) == 0:
        return jsonify({"error": "Uploaded image file is empty."}), 400

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img.verify()
    except Exception:
        return jsonify({"error": "Invalid or corrupt image file."}), 400

    knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
    result = analyze_product_image(image_bytes, knowledge_base, category=category)
    return jsonify(result)


def _is_allowed_image(mimetype, filename):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    allowed_mimetypes = {"image/jpeg", "image/png", "image/webp", "application/octet-stream"}
    lower_name = filename.lower()
    return (
        any(lower_name.endswith(ext) for ext in allowed_extensions)
        and mimetype in allowed_mimetypes
    )

