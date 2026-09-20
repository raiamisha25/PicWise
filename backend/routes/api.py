import io
from flask import Blueprint, current_app, jsonify, request
from PIL import Image

from backend.services.analysis_service import analyze_product_image
from backend.services.food_analysis_service import (
    analyze_food,
    extract_food_data,
    assess_confirmed_food,
)
from backend.services.personal_care_analysis_service import analyze_personal_care
from backend.services.food_status_service import map_food_analysis_presentation

api_bp = Blueprint("api", __name__, url_prefix="/api")


MAX_IMAGE_SIZE_BYTES = 16 * 1024 * 1024  # 16 MB ceiling


@api_bp.post("/food/extract")
def extract_food_endpoint():
    """
    Step 1 of the two-stage food analysis workflow:
    Accepts one or more product images (via 'images[]', 'images', or 'image').
    Executes OCR and extracts detected ingredients and packaging nutrition facts.
    Returns structured data for user confirmation/editing prior to final assessment.
    """
    category = request.form.get("category")
    if not category or not category.strip():
        return jsonify({"error": "Product category is required in form field 'category'.", "success": False}), 400
    category = category.strip().lower()
    if category != "food":
        return jsonify({
            "error": f"Invalid category '{category}'. This endpoint strictly handles 'food' analysis.",
            "success": False,
        }), 400

    files = request.files.getlist("images[]") or request.files.getlist("images")
    if not files:
        single = request.files.get("image")
        if single:
            files = [single]

    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "Image file is required in form field 'images[]' or 'image'.", "success": False}), 400

    if all(not _is_allowed_image(f.mimetype, f.filename or "") for f in files):
        return jsonify({"error": "Only JPG, JPEG, PNG, and WEBP images are supported.", "success": False}), 400

    knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
    extracted_products = []

    for idx, image in enumerate(files):
        prod_id = f"product_{idx + 1}"
        fname = image.filename or f"image_{idx + 1}.jpg"

        if not _is_allowed_image(image.mimetype, fname):
            extracted_products.append({
                "product_id": prod_id,
                "product_index": idx,
                "filename": fname,
                "success": False,
                "ingredients": [],
                "raw_ingredients": [],
                "raw_ingredient_items": [],
                "nutrition": None,
                "raw_text": {},
                "ocr_status": "error",
                "warnings": [],
                "errors": [f"Only JPG, JPEG, PNG, and WEBP images are supported for '{fname}'."],
            })
            continue

        image_bytes = image.read()
        if not image_bytes or len(image_bytes) == 0:
            extracted_products.append({
                "product_id": prod_id,
                "product_index": idx,
                "filename": fname,
                "success": False,
                "ingredients": [],
                "raw_ingredients": [],
                "raw_ingredient_items": [],
                "nutrition": None,
                "raw_text": {},
                "ocr_status": "error",
                "warnings": [],
                "errors": [f"Uploaded image '{fname}' is empty."],
            })
            continue

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            extracted_products.append({
                "product_id": prod_id,
                "product_index": idx,
                "filename": fname,
                "success": False,
                "ingredients": [],
                "raw_ingredients": [],
                "raw_ingredient_items": [],
                "nutrition": None,
                "raw_text": {},
                "ocr_status": "error",
                "warnings": [],
                "errors": [f"Image '{fname}' exceeds the maximum allowed size of 16MB."],
            })
            continue

        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_img.verify()
        except Exception:
            extracted_products.append({
                "product_id": prod_id,
                "product_index": idx,
                "filename": fname,
                "success": False,
                "ingredients": [],
                "raw_ingredients": [],
                "raw_ingredient_items": [],
                "nutrition": None,
                "raw_text": {},
                "ocr_status": "error",
                "warnings": [],
                "errors": [f"Invalid or corrupt image file '{fname}'."],
            })
            continue

        try:
            extract_res = extract_food_data(image_bytes, category="food", knowledge_base=knowledge_base)
            raw_ing_list = []
            for item in extract_res.get("raw_ingredients", []):
                tname = (
                    item.get("matched_name")
                    or item.get("raw_text")
                    or item.get("ocr_text")
                    or item.get("name")
                    or ""
                ).strip()
                if tname and tname not in raw_ing_list:
                    raw_ing_list.append(tname)

            extracted_products.append({
                "product_id": prod_id,
                "product_index": idx,
                "filename": fname,
                "success": extract_res.get("success", False),
                "ingredients": raw_ing_list,
                "raw_ingredients": raw_ing_list,
                "raw_ingredient_items": extract_res.get("raw_ingredients", []),
                "nutrition": extract_res.get("nutrition"),
                "raw_text": extract_res.get("raw_text", {}),
                "ocr_status": "success" if extract_res.get("success") else "error",
                "warnings": extract_res.get("warnings", []),
                "errors": extract_res.get("errors", []),
            })
        except Exception as exc:
            current_app.logger.error(f"Error extracting product '{fname}': {exc}", exc_info=True)
            extracted_products.append({
                "product_id": prod_id,
                "product_index": idx,
                "filename": fname,
                "success": False,
                "ingredients": [],
                "raw_ingredients": [],
                "raw_ingredient_items": [],
                "nutrition": None,
                "raw_text": {},
                "ocr_status": "error",
                "warnings": [],
                "errors": [f"Extraction failed for '{fname}': {str(exc)}"],
            })

    return jsonify({
        "success": True,
        "products": extracted_products,
    }), 200


@api_bp.post("/food/assess")
def assess_food_endpoint():
    """
    Step 2 of the two-stage food analysis workflow:
    Accepts JSON list of products with user-confirmed ingredient lists and extracted nutrition facts.
    Executes Food Safety ML and Allergy lookup on confirmed ingredients, deterministic Nutrition
    scoring on package nutrition facts, and independent presentation mapping.
    """
    payload = request.get_json(silent=True) or {}
    products_input = payload.get("products")

    if not products_input or not isinstance(products_input, list):
        return jsonify({
            "error": "Request body must contain a 'products' array.",
            "success": False,
        }), 400

    knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
    assessed_products = []

    for idx, p in enumerate(products_input):
        prod_id = p.get("product_id") or f"product_{idx + 1}"
        prod_idx = p.get("product_index", idx)
        fname = p.get("filename") or f"product_{idx + 1}"
        confirmed_ingredients = p.get("confirmed_ingredients", [])
        nutrition_data = p.get("nutrition")
        raw_text = p.get("raw_text") or {}

        try:
            result = assess_confirmed_food(
                confirmed_ingredients=confirmed_ingredients,
                nutrition_data=nutrition_data,
                raw_text=raw_text,
                category="food",
                knowledge_base=knowledge_base,
            )
            res_dict = result.to_dict()
            res_dict["product_id"] = prod_id
            res_dict["product_index"] = prod_idx
            res_dict["filename"] = fname
            res_dict["confirmed_ingredients"] = confirmed_ingredients
            assessed_products.append(res_dict)
        except Exception as exc:
            current_app.logger.error(f"Assessment error for product '{prod_id}': {exc}", exc_info=True)
            assessed_products.append({
                "product_id": prod_id,
                "product_index": prod_idx,
                "filename": fname,
                "category": "food",
                "success": False,
                "food_safety": None,
                "nutrition": None,
                "allergy": None,
                "confirmed_ingredients": confirmed_ingredients,
                "presentation": map_food_analysis_presentation(None, None, None).to_dict(),
                "warnings": [],
                "errors": [f"Assessment failed for '{fname}': {str(exc)}"],
            })

    return jsonify({
        "success": True,
        "products": assessed_products,
    }), 200


@api_bp.post("/food/analyze")
def analyze_food_endpoint():
    """
    Unified / direct analysis endpoint supporting both multi-product uploads ('images[]')
    and single-product uploads ('image').
    Maintains 100% backward compatibility for existing unit tests.
    """
    category = request.form.get("category")
    if not category or not category.strip():
        return jsonify({"error": "Product category is required in form field 'category'.", "success": False}), 400

    category = category.strip().lower()
    if category != "food":
        return jsonify({
            "error": f"Invalid category '{category}'. This endpoint strictly handles 'food' analysis.",
            "success": False,
        }), 400

    files = request.files.getlist("images[]") or request.files.getlist("images")
    is_multi_upload = bool(files)

    if not files:
        single = request.files.get("image")
        if single:
            files = [single]

    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "Image file is required in form field 'image'.", "success": False}), 400

    # Single-file legacy validation
    if not is_multi_upload and len(files) == 1:
        image = files[0]
        if not _is_allowed_image(image.mimetype, image.filename):
            return jsonify({"error": "Only JPG, JPEG, PNG, and WEBP images are supported.", "success": False}), 400

        image_bytes = image.read()
        if not image_bytes or len(image_bytes) == 0:
            return jsonify({"error": "Uploaded image file is empty.", "success": False}), 400

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            return jsonify({
                "error": "Uploaded image file exceeds the maximum allowed size of 16MB.",
                "success": False,
            }), 413

        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_img.verify()
        except Exception:
            return jsonify({"error": "Invalid or corrupt image file.", "success": False}), 400

        try:
            knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
            result = analyze_food(image_bytes, category=category, knowledge_base=knowledge_base)
            res_dict = result.to_dict()
            res_dict["product_id"] = "product_1"
            res_dict["filename"] = image.filename
            res_dict["products"] = [dict(res_dict)]
            return jsonify(res_dict), 200
        except Exception as exc:
            current_app.logger.error(f"Unexpected error in /api/food/analyze: {exc}", exc_info=True)
            return jsonify({
                "error": "An unexpected server error occurred. Please try again.",
                "success": False,
            }), 500

    # Multi-file batch processing with per-product failure isolation
    knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
    assessed_products = []

    for idx, image in enumerate(files):
        prod_id = f"product_{idx + 1}"
        fname = image.filename or f"image_{idx + 1}.jpg"

        if not _is_allowed_image(image.mimetype, fname):
            assessed_products.append({
                "product_id": prod_id,
                "filename": fname,
                "category": "food",
                "success": False,
                "food_safety": None,
                "nutrition": None,
                "allergy": None,
                "presentation": map_food_analysis_presentation(None, None, None).to_dict(),
                "warnings": [],
                "errors": [f"Only JPG, JPEG, PNG, and WEBP images are supported for '{fname}'."],
            })
            continue

        image_bytes = image.read()
        if not image_bytes or len(image_bytes) == 0:
            assessed_products.append({
                "product_id": prod_id,
                "filename": fname,
                "category": "food",
                "success": False,
                "food_safety": None,
                "nutrition": None,
                "allergy": None,
                "presentation": map_food_analysis_presentation(None, None, None).to_dict(),
                "warnings": [],
                "errors": [f"Uploaded image '{fname}' is empty."],
            })
            continue

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            assessed_products.append({
                "product_id": prod_id,
                "filename": fname,
                "category": "food",
                "success": False,
                "food_safety": None,
                "nutrition": None,
                "allergy": None,
                "presentation": map_food_analysis_presentation(None, None, None).to_dict(),
                "warnings": [],
                "errors": [f"Image '{fname}' exceeds the maximum allowed size of 16MB."],
            })
            continue

        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_img.verify()
        except Exception:
            assessed_products.append({
                "product_id": prod_id,
                "filename": fname,
                "category": "food",
                "success": False,
                "food_safety": None,
                "nutrition": None,
                "allergy": None,
                "presentation": map_food_analysis_presentation(None, None, None).to_dict(),
                "warnings": [],
                "errors": [f"Invalid or corrupt image file '{fname}'."],
            })
            continue

        try:
            result = analyze_food(image_bytes, category=category, knowledge_base=knowledge_base)
            res_dict = result.to_dict()
            res_dict["product_id"] = prod_id
            res_dict["filename"] = fname
            assessed_products.append(res_dict)
        except Exception as exc:
            current_app.logger.error(f"Unexpected error analyzing '{fname}': {exc}", exc_info=True)
            assessed_products.append({
                "product_id": prod_id,
                "filename": fname,
                "category": "food",
                "success": False,
                "food_safety": None,
                "nutrition": None,
                "allergy": None,
                "presentation": map_food_analysis_presentation(None, None, None).to_dict(),
                "warnings": [],
                "errors": [f"Analysis failed for '{fname}': {str(exc)}"],
            })

    return jsonify({
        "success": True,
        "category": "food",
        "products": assessed_products,
    }), 200


@api_bp.post("/personal-care/analyze")
def analyze_personal_care_endpoint():
    category = request.form.get("category")
    if not category or not category.strip():
        return jsonify({"error": "Product category is required in form field 'category'.", "success": False}), 400

    category = category.strip().lower()
    if category != "personal_care":
        return jsonify({
            "error": f"Invalid category '{category}'. This endpoint strictly handles 'personal_care' analysis.",
            "success": False,
        }), 400

    image = request.files.get("image")
    if image is None or image.filename == "":
        return jsonify({"error": "Image file is required in form field 'image'.", "success": False}), 400

    if not _is_allowed_image(image.mimetype, image.filename):
        return jsonify({"error": "Only JPG, JPEG, PNG, and WEBP images are supported.", "success": False}), 400

    image_bytes = image.read()
    if not image_bytes or len(image_bytes) == 0:
        return jsonify({"error": "Uploaded image file is empty.", "success": False}), 400

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        return jsonify({
            "error": "Uploaded image file exceeds the maximum allowed size of 16MB.",
            "success": False,
        }), 413

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img.verify()
    except Exception:
        return jsonify({"error": "Invalid or corrupt image file.", "success": False}), 400

    try:
        knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
        result = analyze_personal_care(image_bytes, category=category, knowledge_base=knowledge_base)
        return jsonify(result.to_dict()), 200
    except Exception as exc:
        current_app.logger.error(f"Unexpected error in /api/personal-care/analyze: {exc}", exc_info=True)
        return jsonify({
            "error": "An unexpected server error occurred. Please try again.",
            "success": False,
        }), 500


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

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        return jsonify({
            "error": "Uploaded image file exceeds the maximum allowed size of 16MB.",
            "success": False,
        }), 413

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img.verify()
    except Exception:
        return jsonify({"error": "Invalid or corrupt image file."}), 400

    try:
        knowledge_base = current_app.config.get("KNOWLEDGE_BASE")
        result = analyze_product_image(image_bytes, knowledge_base, category=category)
        return jsonify(result), 200
    except Exception as exc:
        current_app.logger.error(f"Unexpected error in /api/analyze: {exc}", exc_info=True)
        return jsonify({
            "error": "An unexpected server error occurred. Please try again.",
            "success": False,
        }), 500


def _is_allowed_image(mimetype, filename):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    allowed_mimetypes = {"image/jpeg", "image/png", "image/webp", "application/octet-stream"}
    lower_name = filename.lower()
    return (
        any(lower_name.endswith(ext) for ext in allowed_extensions)
        and mimetype in allowed_mimetypes
    )

