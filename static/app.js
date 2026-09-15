const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
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

let selectedFile = null;

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
  setSelectedFile(event.dataTransfer.files[0]);
});

removeImage.addEventListener("click", () => {
  selectedFile = null;
  input.value = "";
  previewImage.removeAttribute("src");
  previewWrap.classList.add("hidden");
  analyzeButton.disabled = true;
  fileError.textContent = "";
});

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

  loadingState.classList.remove("hidden");
  resultsPanel.classList.add("hidden");
  analyzeButton.disabled = true;

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Analysis failed.");
    }

    renderResults(data);
    resultsPanel.classList.remove("hidden");
  } catch (error) {
    fileError.textContent = error.message;
  } finally {
    loadingState.classList.add("hidden");
    analyzeButton.disabled = false;
  }
});

function setSelectedFile(file) {
  fileError.textContent = "";
  resultsPanel.classList.add("hidden");

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

  selectedFile = file;
  previewImage.src = URL.createObjectURL(file);
  previewWrap.classList.remove("hidden");
  analyzeButton.disabled = false;
}

function renderResults(data) {
  document.querySelector("#productName").textContent = valueOrUnavailable(data.product?.name);
  document.querySelector("#productBrand").textContent = valueOrUnavailable(data.product?.brand);
  document.querySelector("#productDomain").textContent = formatDomain(data.product?.domain);

  renderList("#ingredientsList", data.ingredients, renderIngredient);
  renderList("#foodDetails", foodItems(data.ingredients), renderFoodDetail);

  const isPersonalCare = data.product?.domain === "personal_care";
  const nutritionContainer = document.querySelector("#nutritionList");
  nutritionContainer.innerHTML = "";

  if (isPersonalCare) {
    const naItem = resultItem("Nutrition Facts", [
      ["Status", "Not applicable for personal care products."]
    ]);
    nutritionContainer.appendChild(naItem);
  } else {
    let nutritionItems = [];
    if (data.nutrition && typeof data.nutrition === "object" && !Array.isArray(data.nutrition)) {
      nutritionItems = Object.entries(data.nutrition).map(([key, val]) => {
        let valStr = unavailable;
        let per100gStr = null;
        if (val && typeof val === "object") {
          if (val.value !== undefined) {
            valStr = `${val.value} ${val.unit || ""}`.trim();
          }
          if (val.per_100g && val.per_100g.value !== undefined) {
            per100gStr = `${val.per_100g.value} ${val.per_100g.unit || ""}`.trim();
          }
        } else if (val !== undefined && val !== null) {
          valStr = String(val);
        }
        return {
          nutrient: formatNutrientName(key),
          value: valStr,
          per100g: per100gStr,
        };
      });
    } else if (Array.isArray(data.nutrition)) {
      nutritionItems = data.nutrition;
    }
    renderList("#nutritionList", nutritionItems, renderNutrition);
  }

  renderList("#personalCareList", data.personalCare, renderPersonalCare);
  renderList("#warningsList", data.warnings, renderWarning);
}

function renderList(selector, items, renderer) {
  const container = document.querySelector(selector);
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
  if (item.foodSafety && Number.isFinite(item.foodSafety.confidence)) {
    pairs.push(["Safety confidence", (item.foodSafety.confidence * 100).toFixed(1) + "%"]);
  }
  return resultItem(
    valueOrUnavailable(item.name),
    pairs,
  );
}

function renderFoodDetail(item) {
  return resultItem(
    valueOrUnavailable(item.name),
    [
      ["Health impact", item.healthImpact],
      ["Processing level", item.processingLevel],
      ["Allergy risk", item.allergyRisk],
      ["Safety level", item.safetyLevel],
    ],
  );
}

function renderNutrition(item) {
  const pairs = [];
  if (item.value !== undefined) {
    pairs.push(["Amount", item.value]);
  }
  if (item.per100g) {
    pairs.push(["Per 100g", item.per100g]);
  }
  if (item.role) {
    pairs.push(["Role", item.role]);
  }
  if (item.healthImpact) {
    pairs.push(["Health impact", item.healthImpact]);
  }
  if (pairs.length === 0) {
    pairs.push(["Amount", unavailable]);
  }
  return resultItem(
    valueOrUnavailable(item.nutrient || item.name),
    pairs
  );
}

function formatNutrientName(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
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

function foodItems(items) {
  return (items || []).filter((item) => item.domain === "food");
}

function formatDomain(domain) {
  if (domain === "food") return "Food";
  if (domain === "personal_care") return "Personal Care";
  if (domain === "unknown") return "Unknown";
  return unavailable;
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
