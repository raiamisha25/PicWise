from backend.services.ingredient_matching import match_ingredients
from backend.services.nutrition_service import find_relevant_nutrition
from backend.services.ocr_service import extract_text


def analyze_product_image(image_bytes, knowledge_base):
    extracted_text = extract_text(image_bytes)
    ingredients = match_ingredients(extracted_text, knowledge_base)
    nutrition = find_relevant_nutrition(extracted_text, knowledge_base)
    domain = _detect_domain(ingredients)

    return {
        "product": {
            "name": None,
            "brand": None,
            "domain": domain,
        },
        "ingredients": ingredients,
        "nutrition": nutrition if domain in {"food", "unknown"} else [],
        "personalCare": _personal_care_results(ingredients),
        "warnings": _warnings(knowledge_base),
    }


def _detect_domain(ingredients):
    food_count = sum(1 for item in ingredients if item["domain"] == "food")
    personal_care_count = sum(
        1 for item in ingredients if item["domain"] == "personal_care"
    )
    if food_count > personal_care_count:
        return "food"
    if personal_care_count > food_count:
        return "personal_care"
    return "unknown"


def _personal_care_results(ingredients):
    return [
        {
            "ingredient": item["name"],
            "function": item["function"],
            "safetyLevel": item["safetyLevel"],
            "irritationRisk": item["irritationRisk"],
        }
        for item in ingredients
        if item["domain"] == "personal_care"
    ]


def _warnings(knowledge_base):
    warnings = list(knowledge_base.warnings)
    warnings.append("OCR is stubbed for Phase 1; results use placeholder extracted text.")
    return warnings
