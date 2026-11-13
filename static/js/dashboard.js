// ==========================================
// AutoBI - Production Dashboard Client Script
// ==========================================

let allPreviewRows = INITIAL_PREVIEW_DATA || [];
let filteredPreviewRows = [...allPreviewRows];
let currentPage = 1;
let pageSize = 25;

// 1. RENDER INITIAL PLOTLY CHARTS
function renderInitialCharts() {
    const chartElements = document.querySelectorAll(".plotly-chart");
    chartElements.forEach((element) => {
        try {
            if (!element.dataset.chart) return;
            const figure = JSON.parse(element.dataset.chart);
            Plotly.newPlot(
                element,
                figure.data,
                figure.layout,
                { responsive: true, displaylogo: false }
            );
        } catch (error) {
            console.error("Chart rendering error on element:", element.id, error);
        }
    });
}

// 2. TOAST NOTIFICATION SYSTEM
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "error" ? "bi-exclamation-circle" : "bi-check-circle";
    toast.innerHTML = `<i class="bi ${icon}"></i> <span>${message}</span>`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add("toast-fadeout");
        setTimeout(() => toast.remove(), 400);
    }, 3500);
}

// 3. GET SELECTED FILTERS & UPDATE UI BADGES
function collectFilters() {
    const filters = {};
    const filterElements = document.querySelectorAll(".dashboard-filter");
    let totalActive = 0;

    filterElements.forEach((element, index) => {
        const column = element.dataset.column;
        const selectedValues = Array.from(element.selectedOptions).map(opt => opt.value);
        const badge = document.getElementById(`badge-${index + 1}`);

        if (selectedValues.length > 0) {
            filters[column] = selectedValues;
            totalActive++;
            if (badge) {
                badge.textContent = `${selectedValues.length} selected`;
                badge.classList.add("badge-active");
            }
        } else {
            if (badge) {
                badge.textContent = "All";
                badge.classList.remove("badge-active");
            }
        }
    });

    const activeCountElem = document.getElementById("active-filter-count");
    if (activeCountElem) {
        activeCountElem.textContent = totalActive;
    }

    return filters;
}

// 4. UPDATE KPI CARDS
function updateKPIs(kpis) {
    const container = document.getElementById("kpi-container");
    if (!container) return;
    container.innerHTML = "";

    kpis.forEach(kpi => {
        const card = document.createElement("div");
        card.className = "kpi-card";
        const subtitleHtml = kpi.subtitle ? `<small class="kpi-sub">${kpi.subtitle}</small>` : "";
        card.innerHTML = `
            <div class="kpi-icon">
                <i class="bi ${kpi.icon}"></i>
            </div>
            <div>
                <span>${kpi.title}</span>
                <h2>${kpi.value}</h2>
                ${subtitleHtml}
            </div>
        `;
        container.appendChild(card);
    });
}

// 5. UPDATE CHARTS
function updateCharts(charts) {
    const container = document.getElementById("charts-container");
    if (!container) return;
    container.innerHTML = "";

    if (!charts || charts.length === 0) {
        container.innerHTML = `
            <div class="empty-charts-card">
                <i class="bi bi-info-circle"></i>
                <h3>No data matches current filters</h3>
                <p>Try clearing or broadening your filter criteria.</p>
            </div>
        `;
        return;
    }

    charts.forEach((chart, index) => {
        const card = document.createElement("div");
        card.className = "chart-card";

        const chartDiv = document.createElement("div");
        chartDiv.id = `dynamic-chart-${index}`;
        chartDiv.style.width = "100%";
        chartDiv.style.height = "100%";

        card.appendChild(chartDiv);
        container.appendChild(card);

        try {
            const figure = JSON.parse(chart.figure);
            Plotly.newPlot(
                chartDiv,
                figure.data,
                figure.layout,
                { responsive: true, displaylogo: false }
            );
        } catch (e) {
            console.error("Failed to render dynamic chart:", e);
        }
    });
}

// 6. ASYNC FILTER SUBMISSION
let filterDebounceTimer = null;

async function refreshDashboard() {
    const filters = collectFilters();
    const sheetSelector = document.getElementById("sheet-selector");
    const overlay = document.getElementById("chart-loading-overlay");

    if (overlay) overlay.style.display = "flex";

    try {
        const response = await fetch(`/api/filter/${FILE_ID}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                sheet: sheetSelector ? sheetSelector.value : "",
                filters: filters
            })
        });

        const data = await response.json();

        if (!response.ok) {
            showToast(data.error || "Unable to update dashboard.", "error");
            return;
        }

        updateKPIs(data.kpis);
        updateCharts(data.charts);

        if (data.summary) {
            const rowElem = document.getElementById("summary-rows");
            const colElem = document.getElementById("summary-columns");
            const compElem = document.getElementById("summary-completeness");

            if (rowElem) rowElem.textContent = data.summary.rows.toLocaleString();
            if (colElem) colElem.textContent = data.summary.columns;
            if (compElem) compElem.textContent = data.summary.completeness + "%";
        }
    } catch (error) {
        console.error("Filter network error:", error);
        showToast("Error communicating with analytics server.", "error");
    } finally {
        if (overlay) overlay.style.display = "none";
    }
}

function debouncedRefresh() {
    clearTimeout(filterDebounceTimer);
    filterDebounceTimer = setTimeout(refreshDashboard, 200);
}

// 7. DATA PREVIEW TABLE PAGINATION & INSTANT SEARCH
function renderPreviewTable() {
    const tbody = document.getElementById("preview-tbody");
    const info = document.getElementById("preview-info");
    const pageIndicator = document.getElementById("page-indicator");
    const prevBtn = document.getElementById("prev-page-btn");
    const nextBtn = document.getElementById("next-page-btn");

    if (!tbody) return;

    const total = filteredPreviewRows.length;
    const maxPages = Math.max(1, Math.ceil(total / pageSize));
    if (currentPage > maxPages) currentPage = maxPages;

    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, total);
    const pageData = filteredPreviewRows.slice(startIdx, endIdx);

    tbody.innerHTML = "";

    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${COLUMNS.length + 1}" style="text-align: center; color: #94a3b8; padding: 25px;">No rows matching search query</td></tr>`;
    } else {
        pageData.forEach((row, i) => {
            const tr = document.createElement("tr");
            let rowHtml = `<td style="color: #94a3b8; font-size: 11px;">${startIdx + i + 1}</td>`;
            COLUMNS.forEach(col => {
                const val = row[col] !== null && row[col] !== undefined ? row[col] : "";
                rowHtml += `<td>${val}</td>`;
            });
            tr.innerHTML = rowHtml;
            tbody.appendChild(tr);
        });
    }

    if (info) {
        info.textContent = total > 0 
            ? `Showing rows ${startIdx + 1} to ${endIdx} of ${total}`
            : `0 rows found`;
    }
    if (pageIndicator) {
        pageIndicator.textContent = `Page ${currentPage} of ${maxPages}`;
    }
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= maxPages;
}

function filterPreviewRows(query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) {
        filteredPreviewRows = [...allPreviewRows];
    } else {
        filteredPreviewRows = allPreviewRows.filter(row => {
            return COLUMNS.some(col => {
                const val = row[col];
                return val !== null && val !== undefined && String(val).toLowerCase().includes(q);
            });
        });
    }
    currentPage = 1;
    renderPreviewTable();
}

// 8. EVENT ATTACHMENTS
document.addEventListener("DOMContentLoaded", () => {
    renderInitialCharts();
    renderPreviewTable();

    // Slicer filters change listener
    document.querySelectorAll(".dashboard-filter").forEach(element => {
        element.addEventListener("change", debouncedRefresh);
    });

    // Clear filters button
    document.getElementById("clear-filters")?.addEventListener("click", () => {
        document.querySelectorAll(".dashboard-filter").forEach(filter => {
            Array.from(filter.options).forEach(opt => (opt.selected = false));
        });
        debouncedRefresh();
        showToast("Filters reset to default.", "info");
    });

    // Worksheet selector change
    document.getElementById("sheet-selector")?.addEventListener("change", function () {
        const sheet = encodeURIComponent(this.value);
        window.location.href = `/dashboard/${FILE_ID}?sheet=${sheet}`;
    });

    // Preview table search input
    document.getElementById("preview-search")?.addEventListener("input", function () {
        filterPreviewRows(this.value);
    });

    // Page size dropdown
    document.getElementById("preview-page-size")?.addEventListener("change", function () {
        pageSize = parseInt(this.value, 10) || 25;
        currentPage = 1;
        renderPreviewTable();
    });

    // Pagination buttons
    document.getElementById("prev-page-btn")?.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            renderPreviewTable();
        }
    });

    document.getElementById("next-page-btn")?.addEventListener("click", () => {
        const maxPages = Math.ceil(filteredPreviewRows.length / pageSize);
        if (currentPage < maxPages) {
            currentPage++;
            renderPreviewTable();
        }
    });

    // Window resize handler for Plotly charts
    window.addEventListener("resize", () => {
        document.querySelectorAll(".plotly-chart").forEach(elem => {
            Plotly.Plots.resize(elem);
        });
    });
});
