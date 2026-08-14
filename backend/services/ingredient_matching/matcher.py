import re

from backend.services.knowledge_base import normalize_value


STOP_WORDS = {
    "ingredient",
    "ingredients",
    "nutrition",
    "contains",
    "and",
}


def match_ingredients(extracted_text, knowledge_base):
    candidates = _extract_candidates(extracted_text)
    matches = []

    for candidate in candidates:
        normalized = normalize_value(candidate)
        if not normalized or normalized in STOP_WORDS:
            continue

        food_row = knowledge_base.food_index.get(normalized)
        personal_care_row = knowledge_base.personal_care_index.get(normalized)

        if food_row:
            matches.append(_food_match(candidate, food_row))
        elif personal_care_row:
            matches.append(_personal_care_match(candidate, personal_care_row))
        else:
            matches.append(_unmatched(candidate))

    return _dedupe(matches)


def _extract_candidates(text):
    ingredient_text = re.split(r"\bnutrition\s*:", text, flags=re.IGNORECASE)[0]
    cleaned = re.sub(
        r"\bingredients?\s*:", "", ingredient_text, flags=re.IGNORECASE
    )
    parts = re.split(r"[,.;\n]", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _food_match(candidate, row):
    return {
        "name": row.get("Ingredient Name") or candidate,
        "matched": True,
        "confidence": 1.0,
        "domain": "food",
        "safetyLevel": row.get("Safety Level") or None,
        "allergyRisk": row.get("Allergy Risk") or None,
        "healthImpact": row.get("Health Impact") or None,
        "processingLevel": row.get("Processing Level") or None,
        "function": None,
        "irritationRisk": None,
    }


def _personal_care_match(candidate, row):
    return {
        "name": row.get("Ingredient_Name") or candidate,
        "matched": True,
        "confidence": 1.0,
        "domain": "personal_care",
        "safetyLevel": row.get("Safety_Level") or None,
        "allergyRisk": row.get("Allergy_Risk") or None,
        "healthImpact": None,
        "processingLevel": None,
        "function": row.get("Primary_Function") or None,
        "irritationRisk": row.get("Irritation_Risk") or None,
    }


def _unmatched(candidate):
    return {
        "name": candidate,
        "matched": False,
        "confidence": 0.0,
        "domain": "unknown",
        "safetyLevel": None,
        "allergyRisk": None,
        "healthImpact": None,
        "processingLevel": None,
        "function": None,
        "irritationRisk": None,
    }


def _dedupe(matches):
    seen = set()
    unique = []
    for match in matches:
        key = normalize_value(match["name"])
        if key not in seen:
            seen.add(key)
            unique.append(match)
    return unique
