"""
backend/services/food_analysis_service/models.py

Data models and contracts for the PicWise Unified Food Analysis Service.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class FoodSafetyIngredientResult:
    """Individual ingredient food safety assessment."""
    ingredient: str
    risk_class: Optional[str]
    confidence: float
    probabilities: Dict[str, float]
    raw_text: str = ""
    matched_name: Optional[str] = None
    match_type: str = "unmatched"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FoodSafetyResult:
    """Component result for production Food Safety ML inference."""
    status: str  # "success" | "no_ingredients" | "error"
    ingredients: List[Dict[str, Any]] = field(default_factory=list)
    total_ingredients: int = 0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


from backend.services.allergy_service.models import (
    AllergyIngredientResult,
    AllergyResult,
)


@dataclass
class FoodAnalysisResult:
    """
    Unified result of the PicWise Food Analysis Pipeline.
    Combines OCR, Food Safety ML, Nutrition Scoring, and Allergy status.
    """
    category: str
    success: bool
    ocr: Optional[Dict[str, Any]] = None
    food_safety: Optional[Dict[str, Any]] = None
    nutrition: Optional[Dict[str, Any]] = None
    allergy: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        fs_val = self.food_safety
        if hasattr(fs_val, "to_dict"):
            fs_val = fs_val.to_dict()

        al_val = self.allergy
        if hasattr(al_val, "to_dict"):
            al_val = al_val.to_dict()

        nut_val = self.nutrition
        if hasattr(nut_val, "to_dict"):
            nut_val = nut_val.to_dict()

        return {
            "category": self.category,
            "success": self.success,
            "ocr": self.ocr,
            "food_safety": fs_val,
            "nutrition": nut_val,
            "allergy": al_val,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
