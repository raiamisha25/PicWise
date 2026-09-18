"""
backend/services/food_analysis_service/analyzer.py

PicWise Unified Food Analysis Orchestration Service.
Coordinates OCR, Food Safety ML inference, Nutrition Scoring Engine,
and Allergy analysis into a deterministic, unified pipeline.
"""

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


def analyze_food(
    image_bytes: bytes,
    category: str = "food",
    knowledge_base: Optional[Any] = None,
) -> FoodAnalysisResult:
    """
    Orchestrates end-to-end food product analysis.

    Parameters:
        image_bytes: Raw bytes of the uploaded food product image.
        category: Must explicitly be 'food'. Any other category or missing value raises InvalidCategoryError.
        knowledge_base: Optional KnowledgeBase instance for OCR fuzzy matching.

    Returns:
        FoodAnalysisResult: Unified typed result combining OCR, Food Safety, Nutrition,
                            and Allergy components.
    """
    # 1. Category Validation (strictly 'food', no automated category guessing)
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

    # 3. OCR Pipeline Execution
    try:
        # Only pass knowledge_base to OCR if it supports the OCR KB interface (get_ingredient_names)
        ocr_kb = knowledge_base if (knowledge_base and hasattr(knowledge_base, "get_ingredient_names")) else None
        ocr_output = run_ocr(image_bytes, category="food", kb=ocr_kb)
    except Exception as exc:
        # On OCR failure, downstream models are NOT called with fabricated data
        return FoodAnalysisResult(
            category="food",
            success=False,
            ocr=None,
            food_safety=None,
            nutrition=None,
            allergy=None,
            errors=[f"OCR processing failed: {str(exc)}"],
            warnings=[],
        )

    all_warnings: List[str] = []

    # 4. Food Safety ML Inference
    raw_ingredients = ocr_output.get("ingredients", [])
    food_safety_dict: Dict[str, Any]

    if not raw_ingredients:
        no_ing_warning = "No ingredients detected in OCR output."
        all_warnings.append(no_ing_warning)
        food_safety_dict = FoodSafetyResult(
            status="no_ingredients",
            ingredients=[],
            total_ingredients=0,
            warnings=[no_ing_warning],
        ).to_dict()
    else:
        try:
            safety_items: List[Dict[str, Any]] = []
            for item in raw_ingredients:
                target_name = (
                    item.get("matched_name")
                    or item.get("raw_text")
                    or item.get("ocr_text")
                    or item.get("name")
                    or ""
                ).strip()

                if not target_name:
                    continue

                # Production Food Safety ML inference (Frozen TF-IDF + MiniLM + Balanced LogReg)
                pred = predict_food_safety(target_name)

                safety_entry = FoodSafetyIngredientResult(
                    ingredient=pred.get("ingredient") or target_name,
                    risk_class=pred.get("risk_class"),
                    confidence=float(pred.get("confidence", 0.0)),
                    probabilities=pred.get("probabilities", {}),
                    raw_text=item.get("raw_text") or item.get("ocr_text") or "",
                    matched_name=item.get("matched_name"),
                    match_type=item.get("method", "unmatched"),
                )
                safety_items.append(safety_entry.to_dict())

            food_safety_dict = FoodSafetyResult(
                status="success",
                ingredients=safety_items,
                total_ingredients=len(safety_items),
                warnings=[],
            ).to_dict()
        except Exception as exc:
            # Component isolation: food safety failure does not crash the entire food analysis
            err_msg = f"Food safety inference encountered an error: {str(exc)}"
            all_warnings.append(err_msg)
            food_safety_dict = FoodSafetyResult(
                status="error",
                ingredients=[],
                total_ingredients=0,
                warnings=[err_msg],
                error=str(exc),
            ).to_dict()

    # 5. Nutrition Scoring Engine Execution
    raw_nutrition = ocr_output.get("nutrition")
    raw_text_dict = ocr_output.get("raw_text") or {}
    product_text = raw_text_dict.get("all_text", "")
    ingredient_text = raw_text_dict.get("ingredients_text", "")

    nutrition_dict: Dict[str, Any]
    try:
        nutrition_res = calculate_nutrition_score(
            raw_nutrition=raw_nutrition,
            category="food",
            product_text=product_text,
            ingredient_text=ingredient_text,
            knowledge_base=knowledge_base,
        )
        nutrition_dict = nutrition_res if isinstance(nutrition_res, dict) else {}
        if nutrition_dict.get("warnings"):
            all_warnings.extend(nutrition_dict["warnings"])
    except Exception as exc:
        # Component isolation: nutrition error does not crash other components
        nut_err_msg = f"Nutrition scoring engine encountered an error: {str(exc)}"
        all_warnings.append(nut_err_msg)
        nutrition_dict = {
            "nutrition_score": None,
            "status": "error",
            "warnings": [nut_err_msg],
            "error": str(exc),
        }

    # 6. Allergy Pipeline Execution (Deterministic Knowledge Base Lookup)
    allergy_dict: Dict[str, Any]
    try:
        allergy_res = calculate_allergy_risk(
            ingredients=raw_ingredients,
            category="food",
            knowledge_base=knowledge_base,
        )
        allergy_dict = allergy_res.to_dict() if hasattr(allergy_res, "to_dict") else allergy_res
        if allergy_dict.get("warnings"):
            all_warnings.extend(allergy_dict["warnings"])
    except Exception as exc:
        # Component isolation: allergy lookup error does not crash the entire food analysis
        all_err_msg = f"Allergy risk lookup encountered an error: {str(exc)}"
        all_warnings.append(all_err_msg)
        allergy_dict = AllergyResult(
            status="error",
            warnings=[all_err_msg],
            error=str(exc),
        ).to_dict()

    # 7. Assemble Unified Result
    return FoodAnalysisResult(
        category="food",
        success=True,
        ocr=ocr_output,
        food_safety=food_safety_dict,
        nutrition=nutrition_dict,
        allergy=allergy_dict,
        errors=[],
        warnings=all_warnings,
    )
