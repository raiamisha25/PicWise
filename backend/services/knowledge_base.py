import csv
import os
from pathlib import Path


DEFAULT_FOOD_DATA_PATH = "data/food/ingredient_knowledge_base_500_with_alternate_names.csv"
DEFAULT_NUTRITION_DATA_PATH = "data/nutrition/nutrition_knowledge_dataset.csv"
DEFAULT_PERSONAL_CARE_DATA_PATH = (
    "data/personal_care/personal_care_ingredients_dataset_csv.xlsx"
)


class KnowledgeBase:
    def __init__(self, food, nutrition, personal_care, warnings):
        self.food = food
        self.nutrition = nutrition
        self.personal_care = personal_care
        self.warnings = warnings
        self.food_index = _build_index(
            food, "Ingredient Name", "Packaging Names / Alternate Names"
        )
        self.personal_care_index = _build_index(
            personal_care, "Ingredient_Name", None
        )
        self.nutrition_index = _build_index(
            nutrition, "Nutrient", "Alternative / Packaging Names"
        )

    @classmethod
    def from_env(cls):
        food_path = os.getenv("FOOD_DATA_PATH", DEFAULT_FOOD_DATA_PATH)
        nutrition_path = os.getenv("NUTRITION_DATA_PATH", DEFAULT_NUTRITION_DATA_PATH)
        personal_care_path = os.getenv(
            "PERSONAL_CARE_DATA_PATH", DEFAULT_PERSONAL_CARE_DATA_PATH
        )

        warnings = []
        food = _load_csv(food_path, warnings, "food")
        nutrition = _load_csv(nutrition_path, warnings, "nutrition")
        personal_care = _load_table(personal_care_path, warnings, "personal care")
        return cls(food, nutrition, personal_care, warnings)


def normalize_value(value):
    text = "" if value is None else str(value)
    return "".join(char.lower() for char in text.strip() if char.isalnum() or char.isspace())


def _build_index(rows, primary_field, alternate_field):
    index = {}
    for row in rows:
        values = [row.get(primary_field, "")]
        if alternate_field:
            values.extend(row.get(alternate_field, "").split(";"))

        for value in values:
            key = normalize_value(value)
            if key:
                index[key] = row
    return index


def _load_csv(path_value, warnings, label):
    path = Path(path_value)
    if not path.exists():
        warnings.append(f"{label.title()} knowledge base not loaded: {path}")
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_table(path_value, warnings, label):
    path = Path(path_value)
    if not path.exists():
        warnings.append(f"{label.title()} knowledge base not loaded: {path}")
        return []

    if path.suffix.lower() == ".csv":
        return _load_csv(path, warnings, label)

    if path.suffix.lower() == ".xlsx":
        return _load_xlsx(path, warnings, label)

    warnings.append(f"{label.title()} knowledge base has unsupported format: {path}")
    return []


def _load_xlsx(path, warnings, label):
    try:
        from openpyxl import load_workbook
    except ImportError:
        warnings.append(
            f"{label.title()} knowledge base requires openpyxl to read {path.name}."
        )
        return []

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]
    records = []
    for row in rows:
        records.append(
            {
                headers[index]: "" if value is None else str(value)
                for index, value in enumerate(row)
                if index < len(headers) and headers[index]
            }
        )
    workbook.close()
    return records
