"""
tests/test_multi_product_confirmation.py

Comprehensive test suite for the Multi-Product User Confirmation & Editing Flow:
1. POST /api/food/extract:
   - Multi-image file upload queue handling
   - OCR ingredient & nutrition extraction without premature inference
   - Error handling (bad categories, missing files, invalid types)
2. POST /api/food/assess:
   - Assessment on user-confirmed / user-edited ingredients
   - Verification that confirmed ingredients are the single source of truth for both Food Safety & Allergy
   - 3 independent dimensions (Food Safety, Allergy, Nutrition) with no overall score/color/verdict
   - Manual entry handling when OCR detects 0 ingredients
   - Empty ingredient list handling
   - Per-product failure isolation (one product failure does not halt or corrupt other products)
3. POST /api/food/analyze backward compatibility:
   - Single image returns legacy dictionary
   - Multiple images return batch dictionary with failure isolation
"""

import io
import json
import os
import unittest
from unittest.mock import patch, MagicMock

from PIL import Image

from backend import create_app


def _create_dummy_image_bytes(format="JPEG", size=(100, 100), color="white") -> bytes:
    """Helper to generate in-memory image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


class TestMultiProductConfirmationFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.real_food_fixture = os.path.join("tests", "fixtures", "product_food.jpeg")

    # ----------------------------------------------------------------------
    # 1. POST /api/food/extract Tests
    # ----------------------------------------------------------------------
    def test_extract_category_enforcement(self):
        """POST /api/food/extract strictly requires category='food'."""
        dummy = _create_dummy_image_bytes()

        # Missing category
        resp_missing = self.client.post(
            "/api/food/extract",
            data={"images[]": (io.BytesIO(dummy), "test.jpg", "image/jpeg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp_missing.status_code, 400)
        self.assertIn("category is required", resp_missing.get_json()["error"])

        # Invalid category
        resp_inv = self.client.post(
            "/api/food/extract",
            data={
                "images[]": (io.BytesIO(dummy), "test.jpg", "image/jpeg"),
                "category": "personal_care",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp_inv.status_code, 400)
        self.assertIn("strictly handles 'food'", resp_inv.get_json()["error"])

    def test_extract_missing_or_invalid_images(self):
        """POST /api/food/extract validates image existence and extension."""
        # No images
        resp_no_img = self.client.post(
            "/api/food/extract",
            data={"category": "food"},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp_no_img.status_code, 400)
        self.assertIn("Image file is required", resp_no_img.get_json()["error"])

        # Invalid extension
        resp_bad = self.client.post(
            "/api/food/extract",
            data={
                "images[]": (io.BytesIO(b"dummy text"), "notes.txt", "text/plain"),
                "category": "food",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp_bad.status_code, 400)
        self.assertIn("Only JPG, JPEG, PNG, and WEBP", resp_bad.get_json()["error"])

    def test_extract_single_and_multi_images(self):
        """POST /api/food/extract extracts ingredients and nutrition for multiple products."""
        dummy1 = _create_dummy_image_bytes(color="red")
        dummy2 = _create_dummy_image_bytes(color="blue")

        mock_ocr_result_1 = {
            "domain": "food",
            "ingredients": [
                {"ocr_text": "Wheat Flour", "matched_name": "Wheat Flour", "raw_text": "Wheat Flour"},
                {"ocr_text": "Sugar", "matched_name": "Sugar", "raw_text": "Sugar"},
            ],
            "nutrition": {
                "energy": {"value": 400.0, "unit": "kcal", "per_100g": {"value": 400.0, "unit": "kcal"}},
                "total_sugars": {"value": 20.0, "unit": "g", "per_100g": {"value": 20.0, "unit": "g"}},
                "total_fat": {"value": 10.0, "unit": "g", "per_100g": {"value": 10.0, "unit": "g"}},
            },
            "raw_text": {"all_text": "Wheat Flour, Sugar", "ingredients_text": "Wheat Flour, Sugar"},
        }
        mock_ocr_result_2 = {
            "domain": "food",
            "ingredients": [
                {"ocr_text": "Milk", "matched_name": "Milk", "raw_text": "Milk"},
            ],
            "nutrition": None,
            "raw_text": {"all_text": "Milk", "ingredients_text": "Milk"},
        }

        with patch("backend.services.food_analysis_service.analyzer.run_ocr") as mock_run_ocr:
            mock_run_ocr.side_effect = [mock_ocr_result_1, mock_ocr_result_2]

            resp = self.client.post(
                "/api/food/extract",
                data={
                    "category": "food",
                    "images[]": [
                        (io.BytesIO(dummy1), "prod1.jpg", "image/jpeg"),
                        (io.BytesIO(dummy2), "prod2.jpg", "image/jpeg"),
                    ],
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(len(data["products"]), 2)

            # Check product 1
            p1 = data["products"][0]
            self.assertEqual(p1["product_index"], 0)
            self.assertEqual(p1["filename"], "prod1.jpg")
            self.assertEqual(p1["ingredients"], ["Wheat Flour", "Sugar"])
            self.assertIsNotNone(p1["nutrition"])
            self.assertEqual(p1["ocr_status"], "success")

            # Check product 2
            p2 = data["products"][1]
            self.assertEqual(p2["product_index"], 1)
            self.assertEqual(p2["filename"], "prod2.jpg")
            self.assertEqual(p2["ingredients"], ["Milk"])
            self.assertIsNone(p2["nutrition"])
            self.assertEqual(p2["ocr_status"], "success")

    # ----------------------------------------------------------------------
    # 2. POST /api/food/assess Tests
    # ----------------------------------------------------------------------
    def test_assess_validation_and_malformed_requests(self):
        """POST /api/food/assess requires a valid JSON body with a non-empty 'products' array."""
        # Non-JSON
        resp = self.client.post("/api/food/assess", data="not json", content_type="text/plain")
        self.assertEqual(resp.status_code, 400)

        # Empty body
        resp = self.client.post("/api/food/assess", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("products", resp.get_json()["error"])

        # Empty products array
        resp = self.client.post("/api/food/assess", json={"products": []})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("products", resp.get_json()["error"])

    def test_assess_confirmed_ingredients_single_source_of_truth(self):
        """User-confirmed ingredients are passed identically to Food Safety and Allergy."""
        confirmed = ["Refined Wheat Flour (Maida)", "Citric Acid", "Sodium Benzoate"]
        nutrition_data = {
            "energy": {"value": 450.0, "unit": "kcal", "per_100g": {"value": 450.0, "unit": "kcal"}},
            "total_sugars": {"value": 24.0, "unit": "g", "per_100g": {"value": 24.0, "unit": "g"}},
            "total_fat": {"value": 15.0, "unit": "g", "per_100g": {"value": 15.0, "unit": "g"}},
            "saturated_fat": {"value": 6.0, "unit": "g", "per_100g": {"value": 6.0, "unit": "g"}},
            "sodium": {"value": 400.0, "unit": "mg", "per_100g": {"value": 400.0, "unit": "mg"}},
        }

        payload = {
            "products": [
                {
                    "product_index": 0,
                    "filename": "biscuit.jpg",
                    "confirmed_ingredients": confirmed,
                    "nutrition": nutrition_data,
                    "raw_text": {"all_text": "biscuit label"},
                }
            ]
        }

        resp = self.client.post("/api/food/assess", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["products"]), 1)

        product = data["products"][0]
        self.assertEqual(product["product_index"], 0)
        self.assertEqual(product["filename"], "biscuit.jpg")
        self.assertEqual(product["confirmed_ingredients"], confirmed)

        # Verify Food Safety dimension
        fs = product["food_safety"]
        self.assertEqual(fs["status"], "success")
        self.assertEqual(fs["total_ingredients"], 3)
        fs_ingredients = [item["ingredient"] for item in fs["ingredients"]]
        self.assertEqual(fs_ingredients, confirmed)

        # Verify Allergy dimension (single source of truth)
        al = product["allergy"]
        self.assertEqual(al["status"], "success")
        self.assertIn("Refined Wheat Flour (Maida)", al["allergens_detected"])

        # Verify Nutrition dimension (scored independently)
        nut = product["nutrition"]
        self.assertEqual(nut["status"], "scored")
        self.assertIsNotNone(nut["nutrition_score"])
        self.assertGreater(nut["nutrition_score"], 0)

        # Verify presentation structure (3 independent dimensions, NO overall score)
        pres = product["presentation"]
        self.assertIn("food_safety", pres)
        self.assertIn("allergy", pres)
        self.assertIn("nutrition", pres)
        self.assertNotIn("overall_score", pres)
        self.assertNotIn("overall_status", pres)
        self.assertNotIn("overall_color", pres)

    def test_assess_user_edited_ingredients(self):
        """User can edit the ingredient list (add/remove items), and the edited list is analyzed."""
        # User removed "Wheat Flour" and added "Peanuts"
        user_edited = ["Peanuts", "Salt"]

        payload = {
            "products": [
                {
                    "product_index": 0,
                    "filename": "snack.png",
                    "confirmed_ingredients": user_edited,
                    "nutrition": None,
                }
            ]
        }

        resp = self.client.post("/api/food/assess", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        product = data["products"][0]

        self.assertEqual(product["confirmed_ingredients"], user_edited)

        # Food safety evaluated Peanuts and Salt
        fs = product["food_safety"]
        self.assertEqual(fs["total_ingredients"], 2)
        fs_names = [i["ingredient"] for i in fs["ingredients"]]
        self.assertEqual(fs_names, ["Peanuts", "Salt"])

        # Allergy caught Peanuts (High risk allergen)
        al = product["allergy"]
        self.assertEqual(al["product_risk_level"], "High")
        self.assertEqual(al["product_ui_label"], "High Allergy Risk")
        self.assertIn("Peanuts", al["allergens_detected"])

        # Nutrition is unavailable (no data)
        nut = product["nutrition"]
        self.assertEqual(nut["status"], "Insufficient Nutrition Data")
        self.assertEqual(product["presentation"]["nutrition"]["status"], "unavailable")
        self.assertIsNone(nut["nutrition_score"])

    def test_assess_manual_entry_when_ocr_empty(self):
        """When OCR finds 0 ingredients, user enters manual ingredients and assessment succeeds."""
        manual_ingredients = ["Peanuts", "Cocoa Powder", "Sugar"]

        payload = {
            "products": [
                {
                    "product_index": 0,
                    "filename": "chocolate_blank_ocr.png",
                    "confirmed_ingredients": manual_ingredients,
                    "nutrition": None,
                }
            ]
        }

        resp = self.client.post("/api/food/assess", json=payload)
        self.assertEqual(resp.status_code, 200)
        product = resp.get_json()["products"][0]

        self.assertEqual(product["confirmed_ingredients"], manual_ingredients)
        self.assertEqual(product["food_safety"]["total_ingredients"], 3)
        self.assertEqual(product["allergy"]["status"], "success")
        self.assertIn("Peanuts", product["allergy"]["allergens_detected"])

    def test_assess_empty_confirmed_ingredients(self):
        """When user confirms an empty ingredient list, status is 'no_ingredients' without crashing."""
        payload = {
            "products": [
                {
                    "product_index": 0,
                    "filename": "empty.png",
                    "confirmed_ingredients": [],
                    "nutrition": None,
                }
            ]
        }

        resp = self.client.post("/api/food/assess", json=payload)
        self.assertEqual(resp.status_code, 200)
        product = resp.get_json()["products"][0]

        self.assertEqual(product["confirmed_ingredients"], [])
        self.assertEqual(product["food_safety"]["status"], "no_ingredients")
        self.assertEqual(product["allergy"]["status"], "no_ingredients")
        self.assertEqual(product["nutrition"]["status"], "Insufficient Nutrition Data")
        self.assertEqual(product["presentation"]["nutrition"]["status"], "unavailable")

    def test_assess_per_product_failure_isolation(self):
        """If one product encounters an unexpected exception, remaining products still succeed."""
        # Product 0 has valid ingredients; Product 1 triggers an unexpected error in assess_confirmed_food
        payload = {
            "products": [
                {
                    "product_index": 0,
                    "filename": "good.jpg",
                    "confirmed_ingredients": ["Sugar", "Salt"],
                    "nutrition": None,
                },
                {
                    "product_index": 1,
                    "filename": "bad.jpg",
                    "confirmed_ingredients": ["Poison Ivy"],
                    "nutrition": None,
                },
                {
                    "product_index": 2,
                    "filename": "another_good.jpg",
                    "confirmed_ingredients": ["Citric Acid"],
                    "nutrition": None,
                },
            ]
        }

        # Mock assess_confirmed_food to raise an exception ONLY on product 1
        original_assess = None
        from backend.services.food_analysis_service import assess_confirmed_food

        def selective_assess(confirmed_ingredients, *args, **kwargs):
            if "Poison Ivy" in confirmed_ingredients:
                raise RuntimeError("Simulated internal crash for Poison Ivy")
            return assess_confirmed_food(confirmed_ingredients, *args, **kwargs)

        with patch("backend.routes.api.assess_confirmed_food", side_effect=selective_assess):
            resp = self.client.post("/api/food/assess", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(len(data["products"]), 3)

            # Product 0 succeeded
            self.assertTrue(data["products"][0]["success"])
            self.assertEqual(data["products"][0]["food_safety"]["status"], "success")

            # Product 1 failed gracefully without crashing the whole request
            self.assertFalse(data["products"][1]["success"])
            self.assertIn("Simulated internal crash", data["products"][1]["errors"][0])

            # Product 2 succeeded
            self.assertTrue(data["products"][2]["success"])
            self.assertEqual(data["products"][2]["food_safety"]["status"], "success")

    # ----------------------------------------------------------------------
    # 3. Multi-Image POST /api/food/analyze Backward Compatibility
    # ----------------------------------------------------------------------
    def test_analyze_endpoint_multi_images_batch(self):
        """POST /api/food/analyze supports multi-image upload returning batch products array."""
        dummy1 = _create_dummy_image_bytes(color="green")
        dummy2 = _create_dummy_image_bytes(color="yellow")

        with patch("backend.services.food_analysis_service.analyzer.run_ocr") as mock_ocr:
            mock_ocr.return_value = {
                "domain": "food",
                "ingredients": [{"matched_name": "Sugar", "raw_text": "Sugar"}],
                "nutrition": None,
                "raw_text": {"all_text": "Sugar", "ingredients_text": "Sugar"},
            }

            resp = self.client.post(
                "/api/food/analyze",
                data={
                    "category": "food",
                    "images[]": [
                        (io.BytesIO(dummy1), "item1.jpg", "image/jpeg"),
                        (io.BytesIO(dummy2), "item2.jpg", "image/jpeg"),
                    ],
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["category"], "food")
            self.assertIn("products", data)
            self.assertEqual(len(data["products"]), 2)
            self.assertEqual(data["products"][0]["filename"], "item1.jpg")
            self.assertEqual(data["products"][1]["filename"], "item2.jpg")


if __name__ == "__main__":
    unittest.main()
