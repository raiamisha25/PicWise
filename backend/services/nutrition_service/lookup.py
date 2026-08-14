from backend.services.knowledge_base import normalize_value


def find_relevant_nutrition(extracted_text, knowledge_base):
    normalized_text = normalize_value(extracted_text)
    words = set(normalized_text.split())
    nutrition = []

    for key, row in knowledge_base.nutrition_index.items():
        if _mentions_key(key, normalized_text, words):
            nutrition.append(
                {
                    "nutrient": row.get("Nutrient") or key,
                    "role": row.get("Health Role") or None,
                    "healthImpact": row.get("Health Impact") or None,
                }
            )

    return _dedupe(nutrition)


def _mentions_key(key, normalized_text, words):
    if len(key) < 3:
        return False
    if " " in key:
        return f" {key} " in f" {normalized_text} "
    return key in words


def _dedupe(items):
    seen = set()
    unique = []
    for item in items:
        key = normalize_value(item["nutrient"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
