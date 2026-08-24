import os
from pathlib import Path
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

DEFAULT_FOOD_DATA_PATH = "data/food/ingredient_knowledge_base_500_with_alternate_names.csv"
DEFAULT_PERSONAL_CARE_DATA_PATH = "data/personal_care/personal_care_ingredients_dataset_csv.xlsx"
DEFAULT_MODEL_DIR = "backend/ml/models"


def normalize_safety_level(val):
    if pd.isna(val) or not str(val).strip():
        return None
    s = str(val).strip().lower()
    if s in ["very safe"]:
        return "Very Safe"
    elif s in ["safe"]:
        return "Safe"
    elif s in ["moderate", "moderate risk"]:
        return "Moderate Risk"
    elif s in ["risky", "high risk"]:
        return "High Risk"
    return str(val).strip()


def normalize_allergy_risk(val):
    if pd.isna(val) or not str(val).strip():
        return "None"
    s = str(val).strip().lower()
    if s in ["none", "no risk", "n/a", "no"]:
        return "None"
    elif s in ["low"]:
        return "Low"
    elif s in ["medium", "moderate"]:
        return "Medium"
    elif s in ["high"]:
        return "High"
    return str(val).strip().title()


def load_raw_datasets(food_path=None, personal_care_path=None):
    if food_path is None:
        food_path = os.getenv("FOOD_DATA_PATH", DEFAULT_FOOD_DATA_PATH)
    if personal_care_path is None:
        personal_care_path = os.getenv("PERSONAL_CARE_DATA_PATH", DEFAULT_PERSONAL_CARE_DATA_PATH)

    rows = []

    # 1. Load Food Dataset
    food_p = Path(food_path)
    if food_p.exists():
        food_df = pd.read_csv(food_p)
        for _, row in food_df.iterrows():
            primary_name = str(row.get("Ingredient Name", "")).strip()
            safety = row.get("Safety Level")
            allergy = row.get("Allergy Risk")
            category = row.get("Category", "")

            if primary_name:
                rows.append({
                    "ingredient_name": primary_name,
                    "domain": "food",
                    "safety_level_raw": safety,
                    "allergy_risk_raw": allergy,
                    "category": category
                })

            # Process alternate names / packaging names
            alt_names = str(row.get("Packaging Names / Alternate Names", "") or "")
            if alt_names and alt_names.lower() != "nan":
                for alt in alt_names.split(";"):
                    alt_clean = alt.strip()
                    if alt_clean:
                        rows.append({
                            "ingredient_name": alt_clean,
                            "domain": "food",
                            "safety_level_raw": safety,
                            "allergy_risk_raw": allergy,
                            "category": category
                        })

    # 2. Load Personal Care Dataset
    pc_p = Path(personal_care_path)
    if pc_p.exists():
        if pc_p.suffix.lower() == ".xlsx":
            pc_df = pd.read_excel(pc_p)
        else:
            pc_df = pd.read_csv(pc_p)

        for _, row in pc_df.iterrows():
            primary_name = str(row.get("Ingredient_Name", "")).strip()
            safety = row.get("Safety_Level")
            allergy = row.get("Allergy_Risk")
            category = row.get("Ingredient_Category", "")

            if primary_name:
                rows.append({
                    "ingredient_name": primary_name,
                    "domain": "personal_care",
                    "safety_level_raw": safety,
                    "allergy_risk_raw": allergy,
                    "category": category
                })

    df = pd.DataFrame(rows)
    return df


def prepare_unified_dataset(food_path=None, personal_care_path=None):
    df = load_raw_datasets(food_path, personal_care_path)
    
    if df.empty:
        raise ValueError("No data loaded from datasets!")

    # Apply normalizations
    df["safety_level"] = df["safety_level_raw"].apply(normalize_safety_level)
    df["allergy_risk"] = df["allergy_risk_raw"].apply(normalize_allergy_risk)

    # Filter out rows missing safety_level if any
    df = df.dropna(subset=["safety_level"]).copy()

    # Deduplicate exact duplicate text and targets
    df["ingredient_name_lower"] = df["ingredient_name"].str.strip().str.lower()
    df = df.drop_duplicates(subset=["ingredient_name_lower", "safety_level", "allergy_risk"]).copy()

    print("=== UNIFIED DATASET TARGET DISTRIBUTION ===")
    print("\nSafety Level Value Counts:")
    print(df["safety_level"].value_counts())
    print("\nAllergy Risk Value Counts:")
    print(df["allergy_risk"].value_counts())
    print("===========================================\n")

    return df


def build_and_split_data(food_path=None, personal_care_path=None, test_size=0.2, random_state=42, model_dir=DEFAULT_MODEL_DIR):
    df = prepare_unified_dataset(food_path, personal_care_path)

    # Fit TF-IDF Vectorizer on character n-grams
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        sublinear_tf=True
    )
    X = vectorizer.fit_transform(df["ingredient_name"])

    # Fit Label Encoders
    safety_encoder = LabelEncoder()
    y_safety = safety_encoder.fit_transform(df["safety_level"])

    allergy_encoder = LabelEncoder()
    y_allergy = allergy_encoder.fit_transform(df["allergy_risk"])

    # Save Vectorizer and Encoders
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(vectorizer, os.path.join(model_dir, "vectorizer.joblib"))
    joblib.dump(safety_encoder, os.path.join(model_dir, "safety_label_encoder.joblib"))
    joblib.dump(allergy_encoder, os.path.join(model_dir, "allergy_label_encoder.joblib"))

    # Train / Test split
    X_train, X_test, y_safety_train, y_safety_test, y_allergy_train, y_allergy_test = train_test_split(
        X, y_safety, y_allergy,
        test_size=test_size,
        random_state=random_state,
        stratify=y_safety
    )

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_safety_train": y_safety_train,
        "y_safety_test": y_safety_test,
        "y_allergy_train": y_allergy_train,
        "y_allergy_test": y_allergy_test,
        "vectorizer": vectorizer,
        "safety_encoder": safety_encoder,
        "allergy_encoder": allergy_encoder,
        "df": df
    }
