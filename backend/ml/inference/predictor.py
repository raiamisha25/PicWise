import os
import joblib

DEFAULT_MODEL_DIR = "backend/ml/models"

_MODEL_CACHE = {
    "vectorizer": None,
    "safety_model": None,
    "allergy_model": None,
    "safety_encoder": None,
    "allergy_encoder": None,
    "loaded": False
}


def _load_artifacts(model_dir=DEFAULT_MODEL_DIR):
    if _MODEL_CACHE["loaded"]:
        return

    vectorizer_path = os.path.join(model_dir, "vectorizer.joblib")
    safety_model_path = os.path.join(model_dir, "safety_model.joblib")
    allergy_model_path = os.path.join(model_dir, "allergy_model.joblib")
    safety_encoder_path = os.path.join(model_dir, "safety_label_encoder.joblib")
    allergy_encoder_path = os.path.join(model_dir, "allergy_label_encoder.joblib")

    if (os.path.exists(vectorizer_path) and 
        os.path.exists(safety_model_path) and 
        os.path.exists(allergy_model_path) and 
        os.path.exists(safety_encoder_path) and 
        os.path.exists(allergy_encoder_path)):
        
        _MODEL_CACHE["vectorizer"] = joblib.load(vectorizer_path)
        _MODEL_CACHE["safety_model"] = joblib.load(safety_model_path)
        _MODEL_CACHE["allergy_model"] = joblib.load(allergy_model_path)
        _MODEL_CACHE["safety_encoder"] = joblib.load(safety_encoder_path)
        _MODEL_CACHE["allergy_encoder"] = joblib.load(allergy_encoder_path)
        _MODEL_CACHE["loaded"] = True


def predict_ingredient_risk(ingredient_name: str, model_dir=DEFAULT_MODEL_DIR) -> dict:
    """
    Predicts Safety Level and Allergy Risk for a given ingredient name.
    
    Returns:
        dict: {
            "safetyLevel": str or None,
            "allergyRisk": str or None,
            "confidence": float
        }
    """
    if not ingredient_name or not ingredient_name.strip():
        return {
            "safetyLevel": None,
            "allergyRisk": None,
            "confidence": 0.0
        }

    _load_artifacts(model_dir=model_dir)

    if not _MODEL_CACHE["loaded"]:
        # Fallback if models are not yet trained or found
        return {
            "safetyLevel": None,
            "allergyRisk": None,
            "confidence": 0.0
        }

    vectorizer = _MODEL_CACHE["vectorizer"]
    safety_model = _MODEL_CACHE["safety_model"]
    allergy_model = _MODEL_CACHE["allergy_model"]
    safety_encoder = _MODEL_CACHE["safety_encoder"]
    allergy_encoder = _MODEL_CACHE["allergy_encoder"]

    # Transform input text
    X_vec = vectorizer.transform([ingredient_name.strip()])

    # Predict Safety Level
    safety_probs = safety_model.predict_proba(X_vec)[0]
    safety_class_idx = safety_probs.argmax()
    predicted_safety = safety_encoder.inverse_transform([safety_class_idx])[0]
    safety_conf = float(safety_probs[safety_class_idx])

    # Predict Allergy Risk
    allergy_probs = allergy_model.predict_proba(X_vec)[0]
    allergy_class_idx = allergy_probs.argmax()
    predicted_allergy = allergy_encoder.inverse_transform([allergy_class_idx])[0]
    allergy_conf = float(allergy_probs[allergy_class_idx])

    # Overall confidence (geometric mean or average of safety & allergy confidence)
    overall_confidence = round(float((safety_conf + allergy_conf) / 2.0), 4)

    return {
        "safetyLevel": str(predicted_safety),
        "allergyRisk": str(predicted_allergy),
        "confidence": overall_confidence
    }
