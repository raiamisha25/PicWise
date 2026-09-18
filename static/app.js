const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
const maxFileSizeBytes = 16 * 1024 * 1024; // 16 MB
const unavailable = "Information not available";

const form = document.querySelector("#uploadForm");
const input = document.querySelector("#imageInput");
const dropZone = document.querySelector("#dropZone");
const fileError = document.querySelector("#fileError");
const previewWrap = document.querySelector("#previewWrap");
const previewImage = document.querySelector("#previewImage");
const removeImage = document.querySelector("#removeImage");
const analyzeButton = document.querySelector("#analyzeButton");
const loadingState = document.querySelector("#loadingState");
const resultsPanel = document.querySelector("#resultsPanel");

// Food-specific result elements
const foodResultsContainer = document.querySelector("#foodResultsContainer");
const personalCareResultsContainer = document.querySelector("#personalCareResultsContainer");
const foodWarningsBanner = document.querySelector("#foodWarningsBanner");
const foodWarningsList = document.querySelector("#foodWarningsList");

const foodSafetyStatusBadge = document.querySelector("#foodSafetyStatusBadge");
const foodSafetyCount = document.querySelector("#foodSafetyCount");
const foodSafetyIngredientsList = document.querySelector("#foodSafetyIngredientsList");

const nutritionStatusBadge = document.querySelector("#nutritionStatusBadge");
const nutritionScoreValue = document.querySelector("#nutritionScoreValue");
const nutritionScoreDenominator = document.querySelector("#nutritionScoreDenominator");
const nutritionScoreNote = document.querySelector("#nutritionScoreNote");
const nutritionNutrientsList = document.querySelector("#nutritionNutrientsList");

const allergyStatusBadge = document.querySelector("#allergyStatusBadge");
const allergyDetectedList = document.querySelector("#allergyDetectedList");
const allergyEmptyNotice = document.querySelector("#allergyEmptyNotice");

let selectedFile = null;

// Event Listeners
input.addEventListener("change", () => {
  setSelectedFile(input.files[0]);
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
  if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0) {
    setSelectedFile(event.dataTransfer.files[0]);
  }
});

removeImage.addEventListener("click", () => {
  selectedFile = null;
  input.value = "";
  previewImage.removeAttribute("src");
  previewWrap.classList.add("hidden");
  analyzeButton.disabled = true;
  fileError.textContent = "";
  resetResults();
});

// Form Submission
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile) {
    fileError.textContent = "Please select an image before analyzing.";
    return;
  }

  const categoryInput = form.querySelector("input[name='category']:checked");
  const selectedCategory = categoryInput ? categoryInput.value : "";
  if (!selectedCategory) {
    fileError.textContent = "Please select a product category (Food or Personal Care).";
    return;
  }

  const formData = new FormData();
  formData.append("image", selectedFile);
  formData.append("category", selectedCategory);

  setLoadingState(true);
  resetResults();
  fileError.textContent = "";

  try {
    const endpoint = selectedCategory === "food" ? "/api/food/analyze" : "/api/analyze";
    const response = await fetch(endpoint, {
      method: "POST",
      body: formData,
    });

    let data;
    try {
      data = await response.json();
    } catch (parseErr) {
      throw new Error("Received an invalid response from the server.");
    }

    if (!response.ok) {
      const errMsg = (data && data.error) || (data && Array.isArray(data.errors) && data.errors[0]) || "Analysis failed.";
      throw new Error(errMsg);
    }

    if (selectedCategory === "food") {
      renderFoodAnalysis(data);
    } else {
      renderPersonalCareAnalysis(data);
    }

    resultsPanel.classList.remove("hidden");
  } catch (error) {
    fileError.textContent = error.message || "An error occurred during analysis.";
  } finally {
    setLoadingState(false);
  }
});

function setSelectedFile(file) {
  fileError.textContent = "";
  resetResults();

  if (!file) {
    return;
  }

  if (!allowedTypes.includes(file.type)) {
    selectedFile = null;
    input.value = "";
    previewWrap.classList.add("hidden");
    analyzeButton.disabled = true;
    fileError.textContent = "Only JPG, JPEG, PNG, and WEBP images are supported.";
    return;
  }

  if (file.size > maxFileSizeBytes) {
    selectedFile = null;
    input.value = "";
    previewWrap.classList.add("hidden");
    analyzeButton.disabled = true;
    fileError.textContent = "Image exceeds the maximum allowed size of 16MB.";
    return;
  }

  selectedFile = file;
  previewImage.src = URL.createObjectURL(file);
  previewWrap.classList.remove("hidden");
  analyzeButton.disabled = false;
}

function setLoadingState(isLoading) {
  if (isLoading) {
    loadingState.classList.remove("hidden");
    analyzeButton.disabled = true;
  } else {
    loadingState.classList.add("hidden");
    analyzeButton.disabled = !selectedFile;
  }
}

function resetResults() {
  resultsPanel.classList.add("hidden");
  if (foodResultsContainer) foodResultsContainer.classList.add("hidden");
  if (personalCareResultsContainer) personalCareResultsContainer.classList.add("hidden");
}

/* ==========================================================================
   FOOD ANALYSIS RENDERING (Phase 9J)
   Consumes backend presentation object strictly.
   NO overall product health score, NO overall product color.
   ========================================================================== */
function renderFoodAnalysis(data) {
  if (personalCareResultsContainer) personalCareResultsContainer.classList.add("hidden");
  if (foodResultsContainer) foodResultsContainer.classList.remove("hidden");

  const pres = data.presentation || {};

  renderFoodSafetyCard(data, pres.food_safety);
  renderNutritionCard(data, pres.nutrition);
  renderAllergyCard(data, pres.allergy);
  renderFoodWarnings(data.warnings);
}

/**
 * Renders the Food Safety card based strictly on backend presentation status.
 */
function renderFoodSafetyCard(data, fsPres) {
  fsPres = fsPres || {};
  const status = fsPres.color || fsPres.status || "unavailable";
  const label = fsPres.label || "Unavailable";

  foodSafetyStatusBadge.className = `status-pill ${escapeHtml(status)}`;
  foodSafetyStatusBadge.textContent = label;

  const totalCount = data.food_safety?.total_ingredients || (data.food_safety?.ingredients ? data.food_safety.ingredients.length : 0);
  foodSafetyCount.textContent = String(totalCount);

  foodSafetyIngredientsList.innerHTML = "";
  const ingredients = data.food_safety?.ingredients || [];

  if (ingredients.length === 0) {
    const emptyNotice = document.createElement("p");
    emptyNotice.className = "allergy-empty-notice";
    emptyNotice.textContent = "No ingredients detected by OCR.";
    foodSafetyIngredientsList.appendChild(emptyNotice);
    return;
  }

  ingredients.forEach((item) => {
    const row = document.createElement("div");
    row.className = "ingredient-badge-row";

    const itemStatus = item.presentation_status || (item.presentation && item.presentation.status) || "unavailable";
    const itemLabel = (item.presentation && item.presentation.label) || item.risk_class || "Assessed";
    const name = item.ingredient || item.matched_name || item.raw_text || unavailable;
    const confStr = Number.isFinite(item.confidence) ? `Confidence: ${Math.round(item.confidence * 100)}%` : "";

    row.innerHTML = `
      <div class="ingredient-info">
        <span class="ingredient-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
        ${confStr ? `<span class="ingredient-confidence">${escapeHtml(confStr)}</span>` : ""}
      </div>
      <span class="status-pill ${escapeHtml(itemStatus)}">${escapeHtml(itemLabel)}</span>
    `;
    foodSafetyIngredientsList.appendChild(row);
  });
}

/**
 * Renders the Nutrition card based strictly on backend presentation status and score.
 * Never defaults missing data to 0 or red.
 */
function renderNutritionCard(data, nutPres) {
  nutPres = nutPres || {};
  const status = nutPres.color || nutPres.status || "unavailable";
  const label = nutPres.label || "Unavailable";

  nutritionStatusBadge.className = `status-pill ${escapeHtml(status)}`;
  nutritionStatusBadge.textContent = label;

  const score = nutPres.score !== undefined && nutPres.score !== null
    ? nutPres.score
    : (data.nutrition && data.nutrition.nutrition_score !== undefined ? data.nutrition.nutrition_score : null);

  if (typeof score === "number" && !isNaN(score)) {
    const formattedScore = Number.isInteger(score) ? score : score.toFixed(1);
    nutritionScoreValue.textContent = formattedScore;
    nutritionScoreDenominator.classList.remove("hidden");
    nutritionScoreNote.textContent = label;
  } else {
    nutritionScoreValue.textContent = "Unavailable";
    nutritionScoreDenominator.classList.add("hidden");
    nutritionScoreNote.textContent = "Nutrition facts not detected on label";
  }

  // Key nutrients breakdown
  nutritionNutrientsList.innerHTML = "";
  const components = data.nutrition?.components || data.nutrition?.nutrients;

  if (components && typeof components === "object" && Object.keys(components).length > 0) {
    Object.entries(components).forEach(([key, val]) => {
      const card = document.createElement("div");
      card.className = "nutrient-card";
      let displayVal = unavailable;

      if (val && typeof val === "object") {
        if (val.value !== undefined && val.value !== null) {
          displayVal = `${val.value} ${val.unit || "g"}`.trim();
        } else if (val.amount !== undefined && val.amount !== null) {
          displayVal = `${val.amount} ${val.unit || "g"}`.trim();
        }
      } else if (val !== null && val !== undefined) {
        displayVal = String(val);
      }

      card.innerHTML = `
        <span class="nutrient-name">${escapeHtml(formatNutrientName(key))}</span>
        <span class="nutrient-value">${escapeHtml(displayVal)}</span>
      `;
      nutritionNutrientsList.appendChild(card);
    });
  } else {
    const emptyNotice = document.createElement("p");
    emptyNotice.className = "allergy-empty-notice";
    emptyNotice.style.gridColumn = "1 / -1";
    emptyNotice.textContent = "Detailed nutrient breakdown unavailable.";
    nutritionNutrientsList.appendChild(emptyNotice);
  }
}

/**
 * Renders the Allergy Risk card based strictly on backend presentation status.
 * CRITICAL: Renders allergen items ONLY if returned in data.allergy.allergens_detected.
 * Never fabricates or guesses allergens from risk levels.
 */
function renderAllergyCard(data, alPres) {
  alPres = alPres || {};
  const status = alPres.color || alPres.status || "unavailable";
  const label = alPres.label || "Unavailable";

  allergyStatusBadge.className = `status-pill ${escapeHtml(status)}`;
  allergyStatusBadge.textContent = label;

  allergyDetectedList.innerHTML = "";

  const allergensDetected = data.allergy?.allergens_detected;

  if (Array.isArray(allergensDetected) && allergensDetected.length > 0) {
    allergyEmptyNotice.classList.add("hidden");
    allergensDetected.forEach((allergen) => {
      const pill = document.createElement("span");
      pill.className = "allergen-item-pill";
      pill.innerHTML = `
        <svg viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>${escapeHtml(allergen)}</span>
      `;
      allergyDetectedList.appendChild(pill);
    });
  } else {
    allergyEmptyNotice.classList.remove("hidden");
    if (status === "green") {
      allergyEmptyNotice.textContent = "No allergens detected in scanned ingredients.";
    } else if (status === "unavailable") {
      allergyEmptyNotice.textContent = "Allergen information not available.";
    } else {
      allergyEmptyNotice.textContent = "No specific allergens listed by name in scanned text.";
    }
  }
}

/**
 * Renders non-fatal warnings or notices from the backend.
 */
function renderFoodWarnings(warnings) {
  if (Array.isArray(warnings) && warnings.length > 0) {
    foodWarningsList.innerHTML = "";
    warnings.forEach((warn) => {
      const li = document.createElement("li");
      li.textContent = warn;
      foodWarningsList.appendChild(li);
    });
    foodWarningsBanner.classList.remove("hidden");
  } else {
    foodWarningsBanner.classList.add("hidden");
  }
}

/* ==========================================================================
   PERSONAL CARE RENDERING (Backward Compatibility)
   ========================================================================== */
function renderPersonalCareAnalysis(data) {
  if (foodResultsContainer) foodResultsContainer.classList.add("hidden");
  if (personalCareResultsContainer) personalCareResultsContainer.classList.remove("hidden");

  document.querySelector("#productName").textContent = valueOrUnavailable(data.product?.name);
  document.querySelector("#productBrand").textContent = valueOrUnavailable(data.product?.brand);
  document.querySelector("#productDomain").textContent = formatDomain(data.product?.domain);

  renderList("#ingredientsList", data.ingredients, renderIngredient);
  renderList("#personalCareList", data.personalCare, renderPersonalCare);
  renderList("#warningsList", data.warnings, renderWarning);
}

function renderList(selector, items, renderer) {
  const container = document.querySelector(selector);
  if (!container) return;
  container.innerHTML = "";

  if (!items || items.length === 0) {
    container.appendChild(emptyItem());
    return;
  }

  items.forEach((item) => container.appendChild(renderer(item)));
}

function renderIngredient(item) {
  const pairs = [
    ["Matched", item.matched ? "Yes" : "No"],
    ["Confidence", Number.isFinite(item.confidence) ? item.confidence.toFixed(2) : unavailable],
    ["Safety level", item.safetyLevel],
    ["Allergy risk", item.allergyRisk],
  ];
  return resultItem(valueOrUnavailable(item.name), pairs);
}

function renderPersonalCare(item) {
  return resultItem(
    valueOrUnavailable(item.ingredient),
    [
      ["Function", item.function],
      ["Safety level", item.safetyLevel],
      ["Irritation risk", item.irritationRisk],
    ],
  );
}

function renderWarning(text) {
  return resultItem("Warning", [["Message", text]]);
}

function resultItem(title, pairs) {
  const wrapper = document.createElement("article");
  wrapper.className = "result-item";
  wrapper.innerHTML = `
    <h4>${escapeHtml(title)}</h4>
    <div class="detail-grid">
      ${pairs.map(([label, value]) => `
        <div>
          <span class="detail-label">${escapeHtml(label)}</span>
          <span class="detail-value">${escapeHtml(valueOrUnavailable(value))}</span>
        </div>
      `).join("")}
    </div>
  `;
  return wrapper;
}

function emptyItem() {
  return resultItem(unavailable, [["Status", unavailable]]);
}

function formatDomain(domain) {
  if (domain === "food") return "Food";
  if (domain === "personal_care") return "Personal Care";
  if (domain === "unknown") return "Unknown";
  return unavailable;
}

function formatNutrientName(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function valueOrUnavailable(value) {
  return value === null || value === undefined || value === "" ? unavailable : value;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
