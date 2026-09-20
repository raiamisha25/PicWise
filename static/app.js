const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
const maxFileSizeBytes = 16 * 1024 * 1024; // 16 MB
const unavailable = "Information not available";

// DOM Elements
const form = document.querySelector("#uploadForm");
const input = document.querySelector("#imageInput");
const dropZone = document.querySelector("#dropZone");
const fileError = document.querySelector("#fileError");
const productQueueWrap = document.querySelector("#productQueueWrap");
const productQueueList = document.querySelector("#productQueueList");
const queueCountElem = document.querySelector("#queueCount");
const clearQueueBtn = document.querySelector("#clearQueueBtn");
const analyzeButton = document.querySelector("#analyzeButton");
const analyzeBtnText = document.querySelector("#analyzeBtnText");

const loadingState = document.querySelector("#loadingState");
const loadingTitle = document.querySelector("#loadingTitle");
const loadingDesc = document.querySelector("#loadingDesc");

// Confirmation Elements
const confirmationPanel = document.querySelector("#confirmationPanel");
const confirmationProductCounter = document.querySelector("#confirmationProductCounter");
const confirmationProductThumb = document.querySelector("#confirmationProductThumb");
const confirmationProductTitle = document.querySelector("#confirmationProductTitle");
const confirmationProductFilename = document.querySelector("#confirmationProductFilename");

const confirmationDetectedWrap = document.querySelector("#confirmationDetectedWrap");
const confirmationIngredientsChecklist = document.querySelector("#confirmationIngredientsChecklist");
const confirmYesBtn = document.querySelector("#confirmYesBtn");
const confirmEditBtn = document.querySelector("#confirmEditBtn");

const confirmationEditWrap = document.querySelector("#confirmationEditWrap");
const confirmationEditList = document.querySelector("#confirmationEditList");
const confirmationAddIngBtn = document.querySelector("#confirmationAddIngBtn");
const confirmationSaveBtn = document.querySelector("#confirmationSaveBtn");
const confirmationCancelEditBtn = document.querySelector("#confirmationCancelEditBtn");

const confirmationEmptyWrap = document.querySelector("#confirmationEmptyWrap");
const confirmationManualList = document.querySelector("#confirmationManualList");
const confirmationManualAddBtn = document.querySelector("#confirmationManualAddBtn");
const confirmationManualContinueBtn = document.querySelector("#confirmationManualContinueBtn");

// Results Elements
const resultsPanel = document.querySelector("#resultsPanel");
const foodResultsContainer = document.querySelector("#foodResultsContainer");
const multiProductResultsGrid = document.querySelector("#multiProductResultsGrid");
const personalCareResultsContainer = document.querySelector("#personalCareResultsContainer");

// Personal Care-specific result elements
const pcWarningsBanner = document.querySelector("#pcWarningsBanner");
const pcWarningsList = document.querySelector("#pcWarningsList");
const pcSafetyStatusBadge = document.querySelector("#pcSafetyStatusBadge");
const pcSafetyCount = document.querySelector("#pcSafetyCount");
const pcSafetyIngredientsList = document.querySelector("#pcSafetyIngredientsList");
const pcAllergyStatusBadge = document.querySelector("#pcAllergyStatusBadge");
const pcAllergyCount = document.querySelector("#pcAllergyCount");
const pcAllergyIngredientsList = document.querySelector("#pcAllergyIngredientsList");
const pcIrritationStatusBadge = document.querySelector("#pcIrritationStatusBadge");
const pcIrritationCount = document.querySelector("#pcIrritationCount");
const pcIrritationIngredientsList = document.querySelector("#pcIrritationIngredientsList");

// State
let productQueue = [];
let isAnalyzing = false;

// Confirmation State
let currentConfirmIndex = 0;
let extractedProducts = [];
let confirmedProducts = [];

// ==========================================================================
// Event Listeners: Product Queue
// ==========================================================================
input.addEventListener("change", () => {
  if (input.files && input.files.length > 0) {
    addFilesToQueue(Array.from(input.files));
    input.value = "";
  }
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
    addFilesToQueue(Array.from(event.dataTransfer.files));
  }
});

clearQueueBtn.addEventListener("click", () => {
  clearProductQueue();
});

// Category Switch: Clear results & errors
const categoryRadios = form.querySelectorAll("input[name='category']");
categoryRadios.forEach((radio) => {
  radio.addEventListener("change", () => {
    resetResults();
    fileError.textContent = "";
  });
});

function addFilesToQueue(files) {
  fileError.textContent = "";
  let addedCount = 0;

  files.forEach((file) => {
    if (file.size === 0) {
      fileError.textContent = `Skipped '${file.name}': file is empty.`;
      return;
    }
    if (!allowedTypes.includes(file.type)) {
      fileError.textContent = `Skipped '${file.name}': only JPG, JPEG, PNG, and WEBP are supported.`;
      return;
    }
    if (file.size > maxFileSizeBytes) {
      fileError.textContent = `Skipped '${file.name}': exceeds maximum size of 16MB.`;
      return;
    }

    const id = "prod_" + Date.now() + "_" + Math.random().toString(36).substr(2, 7);
    const previewUrl = URL.createObjectURL(file);
    productQueue.push({
      id: id,
      file: file,
      name: file.name,
      previewUrl: previewUrl,
    });
    addedCount++;
  });

  renderProductQueue();
}

function removeProductFromQueue(id) {
  const item = productQueue.find((p) => p.id === id);
  if (item && item.previewUrl) {
    URL.revokeObjectURL(item.previewUrl);
  }
  productQueue = productQueue.filter((p) => p.id !== id);
  renderProductQueue();
}

function clearProductQueue() {
  productQueue.forEach((p) => {
    if (p.previewUrl) URL.revokeObjectURL(p.previewUrl);
  });
  productQueue = [];
  renderProductQueue();
  resetResults();
}

function renderProductQueue() {
  if (productQueue.length === 0) {
    productQueueWrap.classList.add("hidden");
    analyzeButton.disabled = true;
    if (analyzeBtnText) analyzeBtnText.textContent = "Analyze All Products";
    if (queueCountElem) queueCountElem.textContent = "0";
    return;
  }

  productQueueWrap.classList.remove("hidden");
  analyzeButton.disabled = false;
  if (queueCountElem) queueCountElem.textContent = String(productQueue.length);
  if (analyzeBtnText) {
    analyzeBtnText.textContent = `Analyze All Products (${productQueue.length})`;
  }

  productQueueList.innerHTML = "";
  productQueue.forEach((prod, index) => {
    const itemEl = document.createElement("div");
    itemEl.className = "queue-item";
    itemEl.innerHTML = `
      <div class="queue-item-left">
        <img src="${prod.previewUrl}" alt="Preview" class="queue-thumb">
        <div class="queue-item-meta">
          <strong class="queue-product-title">Product ${index + 1}</strong>
          <span class="queue-filename" title="${escapeHtml(prod.name)}">${escapeHtml(prod.name)}</span>
        </div>
      </div>
      <button type="button" class="secondary-action queue-remove-btn" title="Remove product">Remove</button>
    `;

    itemEl.querySelector(".queue-remove-btn").addEventListener("click", () => {
      removeProductFromQueue(prod.id);
    });

    productQueueList.appendChild(itemEl);
  });
}

// ==========================================================================
// Form Submission & Multi-Stage Orchestration
// ==========================================================================
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isAnalyzing) return;

  if (productQueue.length === 0) {
    fileError.textContent = "Please add at least one product before analyzing.";
    return;
  }

  const categoryInput = form.querySelector("input[name='category']:checked");
  const selectedCategory = categoryInput ? categoryInput.value : "";
  if (!selectedCategory) {
    fileError.textContent = "Please select a product category (Food or Personal Care).";
    return;
  }

  resetResults();
  fileError.textContent = "";

  if (selectedCategory === "personal_care") {
    await runPersonalCareAnalysis();
  } else {
    await runFoodExtractionStage();
  }
});

// ==========================================================================
// Food Stage 1: Extraction via /api/food/extract
// ==========================================================================
async function runFoodExtractionStage() {
  setLoadingState(true, "Extracting label data with OCR...", "PicWise is reading ingredient lists and nutrition facts from your product image(s).");

  const formData = new FormData();
  formData.append("category", "food");
  productQueue.forEach((prod) => {
    formData.append("images[]", prod.file);
  });

  try {
    const response = await fetch("/api/food/extract", {
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
      const errMsg = (data && data.error) || (data && Array.isArray(data.errors) && data.errors[0]) || "Extraction failed.";
      throw new Error(errMsg);
    }

    setLoadingState(false);

    extractedProducts = data.products || [];
    if (extractedProducts.length === 0) {
      throw new Error("No products were returned by the extraction service.");
    }

    // Start user confirmation flow
    confirmedProducts = [];
    currentConfirmIndex = 0;
    startConfirmationFlow();
  } catch (error) {
    setLoadingState(false);
    const networkMsg = "Unable to connect to the server. Please check that PicWise is running and try again.";
    fileError.textContent = (error.message === "Failed to fetch") ? networkMsg : (error.message || "An error occurred during extraction.");
  }
}

// ==========================================================================
// Food Stage 2: User Confirmation & Editing of OCR Ingredients
// ==========================================================================
function startConfirmationFlow() {
  confirmationPanel.classList.remove("hidden");
  showConfirmationForProduct(currentConfirmIndex);
}

function showConfirmationForProduct(index) {
  if (index >= extractedProducts.length) {
    // All products confirmed; proceed to assessment
    runFoodAssessmentStage();
    return;
  }

  const prod = extractedProducts[index];
  const queueItem = productQueue[index] || {};

  // Update header & thumbnail
  confirmationProductCounter.textContent = `Product ${index + 1} of ${extractedProducts.length}`;
  confirmationProductTitle.textContent = `Product ${index + 1}`;
  confirmationProductFilename.textContent = prod.filename || queueItem.name || `product_${index + 1}`;
  if (queueItem.previewUrl) {
    confirmationProductThumb.src = queueItem.previewUrl;
    confirmationProductThumb.classList.remove("hidden");
  } else {
    confirmationProductThumb.classList.add("hidden");
  }

  const rawIngredients = prod.raw_ingredients || [];

  if (rawIngredients.length > 0) {
    // Case A: OCR detected ingredients -> show review checklist
    showDetectedReview(rawIngredients);
  } else {
    // Case B: OCR detected 0 ingredients -> show manual entry
    showManualEntry();
  }
}

function showDetectedReview(ingredients) {
  confirmationDetectedWrap.classList.remove("hidden");
  confirmationEditWrap.classList.add("hidden");
  confirmationEmptyWrap.classList.add("hidden");

  confirmationIngredientsChecklist.innerHTML = "";
  ingredients.forEach((ing, i) => {
    const label = document.createElement("label");
    label.className = "ingredient-check-item";
    label.innerHTML = `
      <input type="checkbox" checked value="${escapeHtml(ing)}" data-index="${i}">
      <span class="ingredient-check-box"></span>
      <span class="ingredient-check-text">${escapeHtml(ing)}</span>
    `;
    confirmationIngredientsChecklist.appendChild(label);
  });
}

function showEditForm(ingredients) {
  confirmationDetectedWrap.classList.add("hidden");
  confirmationEditWrap.classList.remove("hidden");
  confirmationEmptyWrap.classList.add("hidden");

  confirmationEditList.innerHTML = "";
  ingredients.forEach((ing) => {
    addEditableRow(confirmationEditList, ing);
  });
}

function showManualEntry() {
  confirmationDetectedWrap.classList.add("hidden");
  confirmationEditWrap.classList.add("hidden");
  confirmationEmptyWrap.classList.remove("hidden");

  confirmationManualList.innerHTML = "";
  addEditableRow(confirmationManualList, "");
}

function addEditableRow(container, value) {
  const row = document.createElement("div");
  row.className = "ingredient-edit-row";
  row.innerHTML = `
    <input type="text" class="ingredient-edit-input" value="${escapeHtml(value)}" placeholder="Enter ingredient name (e.g. Cocoa Powder)">
    <button type="button" class="secondary-action remove-row-btn" title="Remove ingredient">Remove</button>
  `;
  row.querySelector(".remove-row-btn").addEventListener("click", () => {
    row.remove();
  });
  container.appendChild(row);
  const inputEl = row.querySelector(".ingredient-edit-input");
  if (!value) inputEl.focus();
}

// Confirmation Buttons Handlers
confirmYesBtn.addEventListener("click", () => {
  const checked = [];
  confirmationIngredientsChecklist.querySelectorAll("input[type='checkbox']:checked").forEach((cb) => {
    if (cb.value.trim()) checked.push(cb.value.trim());
  });
  advanceConfirmation(checked);
});

confirmEditBtn.addEventListener("click", () => {
  const currentChecked = [];
  confirmationIngredientsChecklist.querySelectorAll("input[type='checkbox']:checked").forEach((cb) => {
    if (cb.value.trim()) currentChecked.push(cb.value.trim());
  });
  const currentList = currentChecked.length > 0 ? currentChecked : (extractedProducts[currentConfirmIndex]?.raw_ingredients || []);
  showEditForm(currentList);
});

confirmationAddIngBtn.addEventListener("click", () => {
  addEditableRow(confirmationEditList, "");
});

confirmationSaveBtn.addEventListener("click", () => {
  const edited = [];
  confirmationEditList.querySelectorAll(".ingredient-edit-input").forEach((inp) => {
    const val = inp.value.trim();
    if (val) edited.push(val);
  });
  advanceConfirmation(edited);
});

confirmationCancelEditBtn.addEventListener("click", () => {
  const rawIngredients = extractedProducts[currentConfirmIndex]?.raw_ingredients || [];
  showDetectedReview(rawIngredients);
});

confirmationManualAddBtn.addEventListener("click", () => {
  addEditableRow(confirmationManualList, "");
});

confirmationManualContinueBtn.addEventListener("click", () => {
  const manual = [];
  confirmationManualList.querySelectorAll(".ingredient-edit-input").forEach((inp) => {
    const val = inp.value.trim();
    if (val) manual.push(val);
  });
  advanceConfirmation(manual);
});

function advanceConfirmation(confirmedList) {
  const prod = extractedProducts[currentConfirmIndex];
  confirmedProducts.push({
    product_id: prod.product_id,
    filename: prod.filename,
    confirmed_ingredients: confirmedList,
    nutrition: prod.nutrition,
    raw_text: prod.raw_text,
  });

  currentConfirmIndex++;
  showConfirmationForProduct(currentConfirmIndex);
}

// ==========================================================================
// Food Stage 3: Assessment via /api/food/assess
// ==========================================================================
async function runFoodAssessmentStage() {
  confirmationPanel.classList.add("hidden");
  setLoadingState(true, "Analyzing Food Safety, Allergy Risk, and Nutrition...", "PicWise is evaluating confirmed ingredients and packaging nutrition facts.");

  try {
    const response = await fetch("/api/food/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ products: confirmedProducts }),
    });

    let data;
    try {
      data = await response.json();
    } catch (parseErr) {
      throw new Error("Received an invalid response from the server.");
    }

    if (!response.ok) {
      const errMsg = (data && data.error) || (data && Array.isArray(data.errors) && data.errors[0]) || "Assessment failed.";
      throw new Error(errMsg);
    }

    setLoadingState(false);
    renderMultiProductFoodResults(data.products || []);
    resultsPanel.classList.remove("hidden");
  } catch (error) {
    setLoadingState(false);
    const networkMsg = "Unable to connect to the server. Please check that PicWise is running and try again.";
    fileError.textContent = (error.message === "Failed to fetch") ? networkMsg : (error.message || "An error occurred during assessment.");
  }
}

// ==========================================================================
// Render Multi-Product Food Results Cards
// ==========================================================================
function renderMultiProductFoodResults(products) {
  if (personalCareResultsContainer) personalCareResultsContainer.classList.add("hidden");
  if (foodResultsContainer) foodResultsContainer.classList.remove("hidden");

  multiProductResultsGrid.innerHTML = "";

  products.forEach((prod, index) => {
    const queueItem = productQueue[index] || {};
    const pres = prod.presentation || {};
    const fsPres = pres.food_safety || {};
    const alPres = pres.allergy || {};
    const nutPres = pres.nutrition || {};

    const card = document.createElement("div");
    card.className = "product-result-card card";

    // Format Nutrition Score
    const nutScore = nutPres.score !== undefined && nutPres.score !== null ? nutPres.score : prod.nutrition?.nutrition_score;
    const hasNutScore = typeof nutScore === "number" && !isNaN(nutScore);
    const scoreDisplay = hasNutScore ? `${Number.isInteger(nutScore) ? nutScore : nutScore.toFixed(1)} / 100` : "Unavailable";

    const thumbHtml = queueItem.previewUrl
      ? `<img src="${queueItem.previewUrl}" alt="Thumbnail" class="product-card-thumb">`
      : "";

    card.innerHTML = `
      <div class="product-card-header">
        <div class="product-card-title-wrap">
          ${thumbHtml}
          <div>
            <h3 class="product-title">Product ${index + 1}</h3>
            <span class="product-subtitle">${escapeHtml(prod.filename || queueItem.name || "")}</span>
          </div>
        </div>
      </div>

      <!-- Compact Three-Dimension Summary -->
      <div class="product-summary-box">
        <div class="summary-dimension-row">
          <span class="dim-label">Food Safety</span>
          <span class="status-pill ${escapeHtml(fsPres.status || 'unavailable')}">${escapeHtml(fsPres.label || 'Unavailable')}</span>
        </div>
        <div class="summary-dimension-row">
          <span class="dim-label">Allergy Risk</span>
          <span class="status-pill ${escapeHtml(alPres.status || 'unavailable')}">${escapeHtml(alPres.label || 'Unavailable')}</span>
        </div>
        <div class="summary-dimension-row">
          <span class="dim-label">Nutrition</span>
          <span class="status-pill ${escapeHtml(nutPres.status || 'unavailable')}">${escapeHtml(nutPres.label || 'Unavailable')}</span>
        </div>
        <div class="summary-score-row">
          <span class="dim-label">Nutrition Score:</span>
          <strong class="score-text">${escapeHtml(scoreDisplay)}</strong>
        </div>
      </div>

      <!-- Expandable Details Toggle -->
      <div class="details-toggle-row">
        <button type="button" class="secondary-action toggle-details-btn">View Details</button>
      </div>

      <!-- Detailed Breakdown (Initially Hidden) -->
      <div class="product-details-wrap hidden">
        <!-- Confirmed Ingredients -->
        <div class="detail-section">
          <h4 class="detail-heading">Confirmed Ingredients (${(prod.confirmed_ingredients || []).length})</h4>
          <div class="confirmed-ing-tags">
            ${(prod.confirmed_ingredients || []).map(ing => `<span class="ing-tag">${escapeHtml(ing)}</span>`).join("") || '<p class="empty-detail-note">No ingredients confirmed.</p>'}
          </div>
        </div>

        <!-- Food Safety Breakdown -->
        <div class="detail-section">
          <h4 class="detail-heading">Food Safety Breakdown</h4>
          <div class="ingredient-badges-list">
            ${renderFoodSafetyBreakdownHtml(prod.food_safety)}
          </div>
        </div>

        <!-- Detected Allergens -->
        <div class="detail-section">
          <h4 class="detail-heading">Detected Allergens</h4>
          <div class="allergen-pills-wrap">
            ${renderAllergensHtml(prod.allergy)}
          </div>
        </div>

        <!-- Key Nutrients -->
        <div class="detail-section">
          <h4 class="detail-heading">Package Nutrition Facts</h4>
          <div class="nutrients-grid">
            ${renderNutrientsGridHtml(prod.nutrition)}
          </div>
        </div>

        <!-- Notices & Warnings -->
        ${renderProductWarningsHtml(prod.warnings, prod.errors)}
      </div>
    `;

    // Toggle Details Event
    const toggleBtn = card.querySelector(".toggle-details-btn");
    const detailsWrap = card.querySelector(".product-details-wrap");
    toggleBtn.addEventListener("click", () => {
      const isHidden = detailsWrap.classList.contains("hidden");
      if (isHidden) {
        detailsWrap.classList.remove("hidden");
        toggleBtn.textContent = "Hide Details";
      } else {
        detailsWrap.classList.add("hidden");
        toggleBtn.textContent = "View Details";
      }
    });

    multiProductResultsGrid.appendChild(card);
  });
}

function renderFoodSafetyBreakdownHtml(fsData) {
  const ingredients = fsData?.ingredients || [];
  if (ingredients.length === 0) {
    return `<p class="empty-detail-note">No ingredients assessed for food safety.</p>`;
  }

  return ingredients.map((item) => {
    const itemStatus = item.presentation_status || (item.presentation && item.presentation.status) || "unavailable";
    const itemLabel = (item.presentation && item.presentation.label) || item.risk_class || "Unavailable";
    const name = item.ingredient || item.matched_name || item.raw_text || unavailable;
    const confStr = Number.isFinite(item.confidence) && item.confidence > 0 ? `Confidence: ${Math.round(item.confidence * 100)}%` : "";

    return `
      <div class="ingredient-badge-row">
        <div class="ingredient-info">
          <span class="ingredient-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
          ${confStr ? `<span class="ingredient-confidence">${escapeHtml(confStr)}</span>` : ""}
        </div>
        <span class="status-pill ${escapeHtml(itemStatus)}">${escapeHtml(itemLabel)}</span>
      </div>
    `;
  }).join("");
}

function renderAllergensHtml(allergyData) {
  const detected = allergyData?.allergens_detected || [];
  if (detected.length === 0) {
    const status = allergyData?.presentation_status || (allergyData?.presentation && allergyData.presentation.status);
    const msg = status === "green" ? "Allergen-free: no allergens detected." : "No specific allergens detected by name.";
    return `<p class="empty-detail-note">${escapeHtml(msg)}</p>`;
  }

  return detected.map((allergen) => `
    <span class="allergen-item-pill">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
      <span>${escapeHtml(allergen)}</span>
    </span>
  `).join("");
}

function renderNutrientsGridHtml(nutData) {
  const components = nutData?.components || nutData?.nutrients || nutData?.nutrients_evaluated;
  if (Array.isArray(components) && components.length > 0) {
    return components.map(c => `
      <div class="nutrient-card">
        <span class="nutrient-name">${escapeHtml(c.nutrient || formatNutrientName(c.name || ""))}</span>
        <span class="nutrient-value">${escapeHtml(String(c.amount_per_100g !== undefined ? `${c.amount_per_100g} ${c.unit || 'g'}` : c.value || ''))}</span>
      </div>
    `).join("");
  }

  if (components && typeof components === "object" && Object.keys(components).length > 0) {
    return Object.entries(components).map(([key, val]) => {
      let displayVal = unavailable;
      if (val && typeof val === "object") {
        displayVal = `${val.value ?? val.amount ?? ""} ${val.unit || "g"}`.trim();
      } else if (val !== null && val !== undefined) {
        displayVal = String(val);
      }
      return `
        <div class="nutrient-card">
          <span class="nutrient-name">${escapeHtml(formatNutrientName(key))}</span>
          <span class="nutrient-value">${escapeHtml(displayVal)}</span>
        </div>
      `;
    }).join("");
  }

  return `<p class="empty-detail-note" style="grid-column: 1 / -1;">Detailed nutrient breakdown unavailable.</p>`;
}

function renderProductWarningsHtml(warnings, errors) {
  const items = [...(warnings || []), ...(errors || [])];
  if (items.length === 0) return "";

  return `
    <div class="product-warnings-box">
      <strong>Notices & Warnings</strong>
      <ul>
        ${items.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
      </ul>
    </div>
  `;
}

// ==========================================================================
// Personal Care Analysis Workflow (Preserved for compatibility)
// ==========================================================================
async function runPersonalCareAnalysis() {
  const prod = productQueue[0];
  if (!prod) return;

  setLoadingState(true, "Analyzing personal care product...", "PicWise is evaluating cosmetic ingredients for safety, allergy risk, and irritation.");

  const formData = new FormData();
  formData.append("image", prod.file);
  formData.append("category", "personal_care");

  try {
    const response = await fetch("/api/personal-care/analyze", {
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

    setLoadingState(false);
    renderPersonalCareAnalysis(data);
    resultsPanel.classList.remove("hidden");
  } catch (error) {
    setLoadingState(false);
    const networkMsg = "Unable to connect to the server. Please check that PicWise is running and try again.";
    fileError.textContent = (error.message === "Failed to fetch") ? networkMsg : (error.message || "An error occurred during analysis.");
  }
}

function renderPersonalCareAnalysis(data) {
  if (foodResultsContainer) foodResultsContainer.classList.add("hidden");
  if (personalCareResultsContainer) personalCareResultsContainer.classList.remove("hidden");

  const pres = data.presentation || {};
  const ingredients = data.personal_care?.ingredients || [];
  const recognizedCount = data.personal_care?.recognized_ingredients ?? ingredients.filter((i) => i.status === "success").length;
  const totalCount = data.personal_care?.total_ingredients ?? ingredients.length;
  const countDisplay = `${recognizedCount} of ${totalCount}`;

  renderPersonalCareDimensionCard({
    badgeElem: pcSafetyStatusBadge,
    countElem: pcSafetyCount,
    listElem: pcSafetyIngredientsList,
    dimPres: pres.personal_care_safety,
    dimensionKey: "safety",
    ingredients: ingredients,
    countText: countDisplay,
  });

  renderPersonalCareDimensionCard({
    badgeElem: pcAllergyStatusBadge,
    countElem: pcAllergyCount,
    listElem: pcAllergyIngredientsList,
    dimPres: pres.allergy,
    dimensionKey: "allergy",
    ingredients: ingredients,
    countText: countDisplay,
  });

  renderPersonalCareDimensionCard({
    badgeElem: pcIrritationStatusBadge,
    countElem: pcIrritationCount,
    listElem: pcIrritationIngredientsList,
    dimPres: pres.irritation,
    dimensionKey: "irritation",
    ingredients: ingredients,
    countText: countDisplay,
  });

  renderPersonalCareWarnings(data.warnings, data.ocr_quality_warning);
}

function renderPersonalCareDimensionCard({ badgeElem, countElem, listElem, dimPres, dimensionKey, ingredients, countText }) {
  dimPres = dimPres || {};
  const status = dimPres.color || dimPres.status || "unavailable";
  const label = dimPres.label || "Unavailable";

  if (badgeElem) {
    badgeElem.className = `status-pill ${escapeHtml(status)}`;
    badgeElem.textContent = label;
  }
  if (countElem) countElem.textContent = countText;
  if (!listElem) return;
  listElem.innerHTML = "";

  if (!ingredients || ingredients.length === 0) {
    const emptyNotice = document.createElement("p");
    emptyNotice.className = "allergy-empty-notice";
    emptyNotice.textContent = "No ingredients detected by OCR.";
    listElem.appendChild(emptyNotice);
    return;
  }

  ingredients.forEach((item) => {
    const row = document.createElement("div");
    row.className = "ingredient-badge-row";
    const name = item.matched_name || item.raw_text || unavailable;
    const isSuccess = item.status === "success";

    let itemStatus = "unavailable";
    let itemLabel = "Unavailable";
    let confStr = "";

    if (isSuccess) {
      const dimData = item[dimensionKey] || {};
      const itemPres = (item.presentation && item.presentation[dimensionKey]) || {};
      itemStatus = itemPres.color || itemPres.status || "unavailable";
      itemLabel = itemPres.label || dimData.risk_class || "Assessed";
      if (Number.isFinite(dimData.confidence)) {
        confStr = `Confidence: ${Math.round(dimData.confidence * 100)}%`;
      }
    } else {
      itemStatus = "unavailable";
      if (item.status === "ingredient_not_recognized") {
        itemLabel = "Not Recognized";
        confStr = "Unrecognized ingredient";
      } else {
        itemLabel = "Unavailable";
        confStr = item.reason || "Analysis unavailable";
      }
    }

    row.innerHTML = `
      <div class="ingredient-info">
        <span class="ingredient-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
        ${confStr ? `<span class="ingredient-confidence">${escapeHtml(confStr)}</span>` : ""}
      </div>
      <span class="status-pill ${escapeHtml(itemStatus)}">${escapeHtml(itemLabel)}</span>
    `;
    listElem.appendChild(row);
  });
}

function renderPersonalCareWarnings(warnings, ocrQualityWarning) {
  const allWarns = Array.isArray(warnings) ? [...warnings] : [];
  if (ocrQualityWarning && !allWarns.includes(ocrQualityWarning)) {
    allWarns.unshift(ocrQualityWarning);
  }

  if (allWarns.length > 0) {
    if (pcWarningsList) {
      pcWarningsList.innerHTML = "";
      allWarns.forEach((warn) => {
        const li = document.createElement("li");
        li.textContent = warn;
        if (ocrQualityWarning && warn === ocrQualityWarning) {
          li.className = "quality-advisory-item";
          li.style.fontWeight = "600";
        }
        pcWarningsList.appendChild(li);
      });
    }
    if (pcWarningsBanner) pcWarningsBanner.classList.remove("hidden");
  } else {
    if (pcWarningsBanner) pcWarningsBanner.classList.add("hidden");
  }
}

// ==========================================================================
// Helper Functions
// ==========================================================================
function setLoadingState(isLoading, title, desc) {
  isAnalyzing = isLoading;
  if (isLoading) {
    if (loadingTitle && title) loadingTitle.textContent = title;
    if (loadingDesc && desc) loadingDesc.textContent = desc;
    loadingState.classList.remove("hidden");
    analyzeButton.disabled = true;
  } else {
    loadingState.classList.add("hidden");
    analyzeButton.disabled = productQueue.length === 0;
  }
}

function resetResults() {
  resultsPanel.classList.add("hidden");
  confirmationPanel.classList.add("hidden");
  if (foodResultsContainer) foodResultsContainer.classList.add("hidden");
  if (personalCareResultsContainer) personalCareResultsContainer.classList.add("hidden");
  if (multiProductResultsGrid) multiProductResultsGrid.innerHTML = "";
  if (pcWarningsBanner) pcWarningsBanner.classList.add("hidden");
  if (pcWarningsList) pcWarningsList.innerHTML = "";
  if (pcSafetyIngredientsList) pcSafetyIngredientsList.innerHTML = "";
  if (pcAllergyIngredientsList) pcAllergyIngredientsList.innerHTML = "";
  if (pcIrritationIngredientsList) pcIrritationIngredientsList.innerHTML = "";
}

function formatNutrientName(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
