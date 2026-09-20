"""
backend/services/food_analysis_service/analyzer.py

PicWise Unified Food Analysis Orchestration Service.
Coordinates OCR, Food Safety ML inference, Nutrition Scoring Engine,
and Allergy analysis into a deterministic, unified pipeline.
"""

import logging
from typing import Optional, Any, Dict, List

from backend.ml.inference.food_safety_service import predict_food_safety
from backend.services.food_analysis_service.errors import (
    InvalidCategoryError,
    ImageProcessingError,
    OCRError,
)
from backend.services.food_analysis_service.models import (
    FoodAnalysisResult,
    FoodSafetyResult,
    FoodSafetyIngredientResult,
    AllergyResult,
)
from backend.services.nutrition_service import calculate_nutrition_score
from backend.services.ocr_service import run_ocr
from backend.services.allergy_service import calculate_allergy_risk
from backend.services.food_status_service import (
    map_food_safety_status,
    map_allergy_status,
    map_nutrition_status,
    map_food_analysis_presentation,
)

logger = logging.getLogger(__name__)


def extract_food_data(
    image_bytes: bytes,
    category: str = "food",
    knowledge_base: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes the extraction stage: OCR, ingredient detection, and nutrition parsing.
    Returns structured raw extraction data for user confirmation prior to analysis.
    """
    # 1. Category Validation
    if not category or not isinstance(category, str):
        raise InvalidCategoryError("Category is required and must be 'food'.")

    category_norm = category.strip().lower()
    if category_norm != "food":
        raise InvalidCategoryError(
            f"Invalid category '{category}'. The Food Analysis service strictly handles 'food'."
        )

    # 2. Image Byte Validation
    if not image_bytes or len(image_bytes) == 0:
        raise ImageProcessingError("Image bytes are empty or missing.")

    # 3. OCR Execution
    try:
        ocr_kb = knowledge_base if (knowledge_base and hasattr(knowledge_base, "get_ingredient_names")) else None
        ocr_output = run_ocr(image_bytes, category="food", kb=ocr_kb)
    except Exception as exc:
        err_msg = f"OCR processing failed: {str(exc)}"
        logger.error(err_msg, exc_info=True)
        return {
            "success": False,
            "raw_ingredients": [],
            "nutrition": None,
            "raw_text": {},
            "ocr": None,
            "warnings": [],
            "errors": [err_msg],
        }

    raw_ingredients = ocr_output.get("ingredients", [])
    raw_nutrition = ocr_output.get("nutrition")
    raw_text_dict = ocr_output.get("raw_text") or {}

    return {
        "success": True,
        "raw_ingredients": raw_ingredients,
        "nutrition": raw_nutrition,
        "raw_text": raw_text_dict,
        "ocr": ocr_output,
        "warnings": [],
        "errors": [],
    }


def assess_confirmed_food(
    confirmed_ingredients: List[Any],
    nutrition_data: Optional[Dict[str, Any]] = None,
    raw_text: Optional[Dict[str, Any]] = None,
    category: str = "food",
    knowledge_base: Optional[Any] = None,
    ocr_output: Optional[Dict[str, Any]] = None,
) -> FoodAnalysisResult:
    """
    Executes the downstream assessment stage: Food Safety ML and Allergy lookup
    on confirmed ingredients, deterministic Nutrition scoring on package nutrition facts,
    and presentation mapping.
    """
    if not category or not isinstance(category, str):
        raise InvalidCategoryError("Category is required and must be 'food'.")

    category_norm = category.strip().lower()
    if category_norm != "food":
        raise InvalidCategoryError(
            f"Invalid category '{category}'. The Food Analysis service strictly handles 'food'."
        )

    all_warnings: List[str] = []
    raw_text_dict = raw_text or {}
    product_text = raw_text_dict.get("all_text", "")
    ingredient_text = raw_text_dict.get("ingredients_text", "")

    # Normalize confirmed ingredients into standardized dict format
    normalized_confirmed: List[Dict[str, Any]] = []
    for item in (confirmed_ingredients or []):
        if isinstance(item, str):
            clean_str = item.strip()
            if clean_str:
                normalized_confirmed.append({
                    "raw_text": clean_str,
                    "matched_name": clean_str,
                    "name": clean_str,
                    "method": "user_confirmed",
                })
        elif isinstance(item, dict):
            name_str = (
                item.get("matched_name")
                or item.get("raw_text")
                or item.get("ocr_text")
                or item.get("name")
                or ""
            ).strip()
            if name_str:
                normalized_confirmed.append({
                    "raw_text": item.get("raw_text") or item.get("ocr_text") or name_str,
                    "matched_name": item.get("matched_name") or name_str,
                    "name": name_str,
                    "method": item.get("method") or "user_confirmed",
                })

    # 1. Food Safety ML Inference
    food_safety_dict: Dict[str, Any]
    if not normalized_confirmed:
        no_ing_warning = "No ingredients detected or confirmed for food safety analysis."
        all_warnings.append(no_ing_warning)
        food_safety_dict = FoodSafetyResult(
            status="no_ingredients",
            ingredients=[],
            total_ingredients=0,
            warnings=[no_ing_warning],
            risk_class=None,
        ).to_dict()
    else:
        try:
            safety_items: List[Dict[str, Any]] = []
            for item in normalized_confirmed:
                target_name = item["name"]
                pred = predict_food_safety(target_name)

                safety_entry = FoodSafetyIngredientResult(
                    ingredient=pred.get("ingredient") or target_name,
                    risk_class=pred.get("risk_class"),
                    confidence=float(pred.get("confidence", 0.0)),
                    probabilities=pred.get("probabilities", {}),
                    raw_text=item.get("raw_text", ""),
                    matched_name=item.get("matched_name"),
                    match_type=item.get("method", "user_confirmed"),
                )
                entry_dict = safety_entry.to_dict()
                ing_pres = map_food_safety_status(pred.get("risk_class"))
                entry_dict["presentation_status"] = ing_pres.status
                entry_dict["presentation"] = ing_pres.to_dict()
                safety_items.append(entry_dict)

            # Worst-case product risk class aggregation:
            # High Risk > Moderate Risk > Safe > Very Safe
            product_risk_class = None
            if safety_items:
                risk_order = {
                    "high risk": (4, "High Risk"),
                    "moderate risk": (3, "Moderate Risk"),
                    "safe": (2, "Safe"),
                    "very safe": (1, "Very Safe"),
                }
                max_rank = 0
                for item in safety_items:
                    rc = item.get("risk_class")
                    if rc and isinstance(rc, str):
                        rank, canonical_rc = risk_order.get(rc.lower().strip(), (0, None))
                        if rank > max_rank:
                            max_rank = rank
                            product_risk_class = canonical_rc

            food_safety_dict = FoodSafetyResult(
                status="success",
                ingredients=safety_items,
                total_ingredients=len(safety_items),
                warnings=[],
                risk_class=product_risk_class,
            ).to_dict()
        except Exception as exc:
            err_msg = f"Food safety inference encountered an error: {str(exc)}"
            logger.error(err_msg, exc_info=True)
            all_warnings.append(err_msg)
            food_safety_dict = FoodSafetyResult(
                status="error",
                ingredients=[],
                total_ingredients=0,
                warnings=[err_msg],
                error=str(exc),
                risk_class=None,
            ).to_dict()

    fs_pres = map_food_safety_status(food_safety_dict.get("risk_class"))
    food_safety_dict["presentation_status"] = fs_pres.status
    food_safety_dict["presentation"] = fs_pres.to_dict()

    # 2. Nutrition Scoring Engine Execution (from package nutrition facts)
    nutrition_dict: Dict[str, Any]
    try:
        nutrition_res = calculate_nutrition_score(
            raw_nutrition=nutrition_data,
            category="food",
            product_text=product_text,
            ingredient_text=ingredient_text,
            knowledge_base=knowledge_base,
        )
        nutrition_dict = nutrition_res if isinstance(nutrition_res, dict) else {}
        if nutrition_dict.get("warnings"):
            all_warnings.extend(nutrition_dict["warnings"])
    except Exception as exc:
        nut_err_msg = f"Nutrition scoring engine encountered an error: {str(exc)}"
        logger.error(nut_err_msg, exc_info=True)
        all_warnings.append(nut_err_msg)
        nutrition_dict = {
            "nutrition_score": None,
            "status": "error",
            "warnings": [nut_err_msg],
            "error": str(exc),
        }

    nut_score = nutrition_dict.get("nutrition_score")
    nut_pres = map_nutrition_status(
        score=nut_score,
        raw_status=nutrition_dict.get("status"),
    )
    nutrition_dict["presentation_status"] = nut_pres.status
    nutrition_dict["presentation"] = nut_pres.to_dict()
    if "score" not in nutrition_dict:
        nutrition_dict["score"] = nut_score
    if "label" not in nutrition_dict:
        nutrition_dict["label"] = nut_pres.label

    # 3. Allergy Pipeline Execution (Deterministic KB lookup on confirmed ingredients)
    allergy_dict: Dict[str, Any]
    try:
        allergy_res = calculate_allergy_risk(
            ingredients=normalized_confirmed,
            category="food",
            knowledge_base=knowledge_base,
        )
        allergy_dict = allergy_res.to_dict() if hasattr(allergy_res, "to_dict") else allergy_res
        if allergy_dict.get("warnings"):
            all_warnings.extend(allergy_dict["warnings"])
    except Exception as exc:
        all_err_msg = f"Allergy risk lookup encountered an error: {str(exc)}"
        logger.error(all_err_msg, exc_info=True)
        all_warnings.append(all_err_msg)
        allergy_dict = AllergyResult(
            status="error",
            warnings=[all_err_msg],
            error=str(exc),
        ).to_dict()

    al_risk = allergy_dict.get("product_risk_level") or allergy_dict.get("risk_level")
    al_pres = map_allergy_status(
        risk_level=al_risk,
        raw_status=allergy_dict.get("status"),
    )
    allergy_dict["presentation_status"] = al_pres.status
    allergy_dict["presentation"] = al_pres.to_dict()
    if "risk_level" not in allergy_dict and al_risk:
        allergy_dict["risk_level"] = al_risk
    if "ui_label" not in allergy_dict and allergy_dict.get("product_ui_label"):
        allergy_dict["ui_label"] = allergy_dict.get("product_ui_label")

    # 4. Presentation Status Mapping across independent dimensions
    presentation_dict: Optional[Dict[str, Any]] = None
    try:
        presentation_obj = map_food_analysis_presentation(
            food_safety=food_safety_dict,
            allergy=allergy_dict,
            nutrition=nutrition_dict,
        )
        presentation_dict = presentation_obj.to_dict()
    except Exception as exc:
        pres_err_msg = f"Presentation status mapping failed: {str(exc)}"
        logger.error(pres_err_msg, exc_info=True)
        all_warnings.append(pres_err_msg)
        presentation_dict = {
            "food_safety": {"status": "unavailable", "label": "Unavailable"},
            "allergy": {"status": "unavailable", "label": "Unavailable"},
            "nutrition": {"status": "unavailable", "label": "Unavailable", "score": None},
        }

    logger.info(
        "Food assessment completed. Confirmed ingredients: %d, Allergy: %s, Nutrition score: %s",
        len(normalized_confirmed),
        allergy_dict.get("presentation_status"),
        str(nutrition_dict.get("nutrition_score")),
    )
    return FoodAnalysisResult(
        category="food",
        success=True,
        ocr=ocr_output,
        food_safety=food_safety_dict,
        nutrition=nutrition_dict,
        allergy=allergy_dict,
        errors=[],
        warnings=all_warnings,
        presentation=presentation_dict,
    )


def analyze_food(
    image_bytes: bytes,
    category: str = "food",
    knowledge_base: Optional[Any] = None,
) -> FoodAnalysisResult:
    """
    Orchestrates end-to-end food product analysis.
    Direct single-call pipeline (runs extraction then immediate assessment).
    Preserves 100% backward compatibility for existing callers and test suites.
    """
    extract_data = extract_food_data(image_bytes, category=category, knowledge_base=knowledge_base)
    if not extract_data.get("success"):
        return FoodAnalysisResult(
            category="food",
            success=False,
            ocr=None,
            food_safety=None,
            nutrition=None,
            allergy=None,
            errors=extract_data.get("errors", ["OCR processing failed"]),
            warnings=[],
            presentation=map_food_analysis_presentation(None, None, None).to_dict(),
        )

    return assess_confirmed_food(
        confirmed_ingredients=extract_data.get("raw_ingredients", []),
        nutrition_data=extract_data.get("nutrition"),
        raw_text=extract_data.get("raw_text", {}),
        category=category,
        knowledge_base=knowledge_base,
        ocr_output=extract_data.get("ocr"),
    )
