/**
 * script.js - Smart Spending Analytics System (SSAS)
 *
 * Client-side logic:
 *  - Fetching transactions and summary from Flask API
 *  - Rendering transaction ledger and KPI cards
 *  - Add / Edit / Delete transaction operations
 *  - Filtering by category and period
 *  - Toast notifications and modal confirmations
 *
 * API Base URL: /api
 */

'use strict';

// ─── Configuration ────────────────────────────────────────────────────────────
const API = '/api';

// Map category names to CSS class suffixes and emoji icons
const CATEGORY_META = {
  'Food & Dining':    { cls: 'food',      icon: '🍔' },
  'Transportation':   { cls: 'transport', icon: '🚗' },
  'Shopping':         { cls: 'shopping',  icon: '🛍️' },
  'Entertainment':    { cls: 'entertain', icon: '🎬' },
  'Health & Medical': { cls: 'health',    icon: '🏥' },
  'Housing & Rent':   { cls: 'housing',   icon: '🏠' },
  'Utilities':        { cls: 'utilities', icon: '💡' },
  'Education':        { cls: 'education', icon: '📚' },
  'Travel':           { cls: 'travel',    icon: '✈️' },
  'Personal Care':    { cls: 'personal',  icon: '💆' },
  'Subscriptions':    { cls: 'subs',      icon: '📱' },
  'Other':            { cls: 'other',     icon: '📌' },
};

// ─── State ────────────────────────────────────────────────────────────────────
let allExpenses = [];        // Full list from API
let filteredExpenses = [];   // After applying filters
let editingId = null;        // Currently editing expense ID (null = none)
let deleteTargetId = null;   // Expense pending deletion confirmation

// ─── DOM Element References ───────────────────────────────────────────────────
const expenseForm      = document.getElementById('expense-form');
const expenseTbody     = document.getElementById('expense-tbody');
const filterCategory   = document.getElementById('filter-category');
const filterMonth      = document.getElementById('filter-month');
const filterSearch     = document.getElementById('filter-search');   // keyword search
const recordCount      = document.getElementById('record-count');
const deleteModal      = document.getElementById('delete-modal');
const deleteConfirmBtn = document.getElementById('delete-confirm-btn');
const deleteCancelBtn  = document.getElementById('delete-cancel-btn');
const toastContainer   = document.getElementById('toast-container');

// Dashboard card elements
const cardTotal        = document.getElementById('card-total');
const cardCount        = document.getElementById('card-count');
const cardMonthTotal   = document.getElementById('card-month-total');
const cardMonthName    = document.getElementById('card-month-name');
const cardTrend        = document.getElementById('card-trend');

// Summary section elements
const categoryBars     = document.getElementById('category-bars');
const monthlyList      = document.getElementById('monthly-list');
const alertsContainer  = document.getElementById('alerts-container');

// Budget card elements
const cardBudget       = document.getElementById('card-budget');
const cardBudgetMeta   = document.getElementById('card-budget-meta');
const budgetSetRow     = document.getElementById('budget-set-row');
const budgetBarWrap    = document.getElementById('budget-bar-wrap');
const budgetBarFill    = document.getElementById('budget-bar-fill');
const budgetBarSpent   = document.getElementById('budget-bar-spent');
const budgetBarLimit   = document.getElementById('budget-bar-limit');

// Forecast elements
const cardForecast     = document.getElementById('card-forecast');
const cardForecastMeta = document.getElementById('card-forecast-meta');
const cardForecastBadge= document.getElementById('card-forecast-badge');
const forecastDetail   = document.getElementById('forecast-detail');
const forecastConfBadge= document.getElementById('forecast-confidence-badge');

// Tracked budget value
let currentBudget = 0;

// Chart instances — kept globally so we can destroy before re-render
let categoryChart = null;
let monthlyChart  = null;
let forecastChart = null;

// ─── Initialization ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Show today's date in the topbar
  document.getElementById('current-date').textContent =
    new Date().toLocaleDateString('en-US', { weekday:'long', year:'numeric', month:'long', day:'numeric' });

  // Set user avatar letter
  const uname = document.getElementById('sidebar-username');
  const avatar = document.getElementById('user-avatar-letter');
  if (uname && avatar) avatar.textContent = (uname.textContent || 'U')[0].toUpperCase();

  // Default form date to today
  document.getElementById('expense-date').valueAsDate = new Date();

  // Load data
  loadExpenses();
  loadSummary();
  loadBudget();
  loadForecast();

  // Form submit
  expenseForm.addEventListener('submit', handleFormSubmit);

  // Filter listeners
  filterCategory.addEventListener('change', applyFilters);
  filterMonth.addEventListener('change', applyFilters);
  if (filterSearch) filterSearch.addEventListener('input', applyFilters);

  // Modal buttons
  deleteConfirmBtn.addEventListener('click', confirmDelete);
  deleteCancelBtn.addEventListener('click', closeDeleteModal);
  deleteModal.addEventListener('click', (e) => { if (e.target === deleteModal) closeDeleteModal(); });

  // Budget save button
  document.getElementById('budget-save-btn').addEventListener('click', saveBudget);
  document.getElementById('budget-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') saveBudget();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// API HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Generic fetch wrapper that handles JSON parsing and error checking.
 * @param {string} url - API endpoint path
 * @param {object} options - fetch options (method, body, headers)
 * @returns {Promise<object>} - Parsed JSON response body
 */
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
  };
  const response = await fetch(url, { ...defaults, ...options });
  const json = await response.json();
  if (!response.ok || !json.success) {
    throw new Error(json.message || `HTTP ${response.status}`);
  }
  return json;
}

// ─────────────────────────────────────────────────────────────────────────────
// LOAD EXPENSES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetch all expenses from the backend and render the table.
 */
async function loadExpenses() {
  showTableLoading();
  try {
    const json = await apiFetch(`${API}/expenses`);
    allExpenses = json.data || [];
    applyFilters();
  } catch (err) {
    showToast(`Failed to load transactions: ${err.message}`, 'error');
    expenseTbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">⚠️</div><p>${err.message}</p></div></td></tr>`;
  }
}

/**
 * Fetch summary statistics and update dashboard cards.
 */
async function loadSummary() {
  try {
    const json = await apiFetch(`${API}/summary`);
    const s = json.data;
    renderDashboardCards(s);
    renderCategoryBars(s.by_category, s.total);
    renderCategoryChart(s.by_category);
    renderMonthlyList(s.monthly);
    renderMonthlyChart(s.monthly);
    renderAlerts(s.alerts || []);
    // Re-render budget bar with updated spend
    renderBudgetCard(currentBudget, s.current_month_total || 0);
  } catch (err) {
    showToast(`Failed to load summary: ${err.message}`, 'error');
  }
}

/**
 * Fetch the user's saved monthly budget from the server.
 */
async function loadBudget() {
  try {
    const json = await apiFetch(`${API}/budget`);
    currentBudget = json.data.monthly_budget || 0;
    // We need the current month spend — get it from summary cache if available
    const summaryJson = await apiFetch(`${API}/summary`);
    const spent = summaryJson.data.current_month_total || 0;
    renderBudgetCard(currentBudget, spent);
  } catch (err) {
    // Non-critical — just show the input
    renderBudgetCard(0, 0);
  }
}

/**
 * Save the monthly budget entered by the user.
 */
async function saveBudget() {
  const input = document.getElementById('budget-input');
  const value = parseFloat(input.value);
  if (isNaN(value) || value < 0) {
    showToast('❌ Please enter a valid positive amount.', 'error');
    return;
  }
  try {
    await apiFetch(`${API}/budget`, {
      method: 'POST',
      body: JSON.stringify({ monthly_budget: value }),
    });
    currentBudget = value;
    const summaryJson = await apiFetch(`${API}/summary`);
    const spent = summaryJson.data.current_month_total || 0;
    renderBudgetCard(currentBudget, spent);
    // Also refresh forecast vs budget
    loadForecast();
    showToast(`✅ Monthly budget set to ₹${value.toFixed(2)}`, 'success');
    input.value = '';
  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
  }
}

/**
 * Fetch spending forecast from the server.
 */
async function loadForecast() {
  try {
    const json = await apiFetch(`${API}/forecast`);
    const f = json.data;
    renderForecastCard(f);
    renderForecastPanel(f);
    renderForecastChart(f);
  } catch (err) {
    if (cardForecast) cardForecast.textContent = 'N/A';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER FUNCTIONS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Apply category and month filters then re-render the table.
 */
function applyFilters() {
  const cat    = filterCategory.value.toLowerCase();
  const month  = filterMonth.value;  // "YYYY-MM" or ""
  const search = filterSearch ? filterSearch.value.trim().toLowerCase() : '';

  filteredExpenses = allExpenses.filter(e => {
    const matchCat    = !cat    || e.category.toLowerCase() === cat;
    const matchMonth  = !month  || (e.date || '').startsWith(month);
    const matchSearch = !search
      || (e.title    || '').toLowerCase().includes(search)
      || (e.notes    || '').toLowerCase().includes(search)
      || (e.category || '').toLowerCase().includes(search);
    return matchCat && matchMonth && matchSearch;
  });

  renderTable(filteredExpenses);
  recordCount.textContent = `${filteredExpenses.length} record${filteredExpenses.length !== 1 ? 's' : ''}`;
}

/**
 * Render the expense rows in the table.
 * @param {Array} expenses
 */
function renderTable(expenses) {
  if (!expenses.length) {
    expenseTbody.innerHTML = `
      <tr><td colspan="7">
        <div class="empty-state">
          <div class="empty-icon">📊</div>
          <p>No transactions yet. Log your first transaction!</p>
        </div>
      </td></tr>`;
    return;
  }

  expenseTbody.innerHTML = expenses.map(e => buildRow(e)).join('');

  // Attach event listeners to all buttons
  expenseTbody.querySelectorAll('.btn-edit-row').forEach(btn =>
    btn.addEventListener('click', () => startEdit(btn.dataset.id)));
  expenseTbody.querySelectorAll('.btn-delete-row').forEach(btn =>
    btn.addEventListener('click', () => openDeleteModal(btn.dataset.id)));
}

/**
 * Build a standard (read-only) table row HTML string.
 * @param {object} e - Expense object
 * @returns {string} HTML string
 */
function buildRow(e) {
  const meta = CATEGORY_META[e.category] || CATEGORY_META['Other'];
  const dateFormatted = e.date
    ? new Date(e.date + 'T00:00:00').toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' })
    : '—';
  return `
    <tr data-id="${e.expense_id}">
      <td>
        <div class="tx-title">${escHtml(e.title)}</div>
        ${e.notes ? `<div class="tx-notes">${escHtml(e.notes)}</div>` : ''}
      </td>
      <td class="amount-cell">₹${Number(e.amount).toFixed(2)}</td>
      <td>
        <span class="badge badge-${meta.cls}">${meta.icon} ${escHtml(e.category)}</span>
      </td>
      <td class="date-cell">${dateFormatted}</td>
      <td class="date-cell">${formatTime(e.created_at)}</td>
      <td>
        <div class="actions-cell">
          <button class="btn btn-sm btn-edit btn-edit-row" data-id="${e.expense_id}" title="Edit">✏️ Edit</button>
          <button class="btn btn-sm btn-delete btn-delete-row" data-id="${e.expense_id}" title="Remove">🗑️ Remove</button>
        </div>
      </td>
    </tr>`;
}

/**
 * Build an editable inline row for the expense being edited.
 * @param {object} e - Expense object
 * @returns {string} HTML string
 */
function buildEditRow(e) {
  const categoryOptions = Object.keys(CATEGORY_META)
    .map(c => `<option value="${c}" ${c === e.category ? 'selected' : ''}>${c}</option>`)
    .join('');
  return `
    <tr data-id="${e.expense_id}" class="editing">
      <td><input class="form-control" id="edit-title" value="${escHtml(e.title)}" placeholder="Title"></td>
      <td><input class="form-control" id="edit-amount" type="number" step="0.01" min="0.01" value="${e.amount}" placeholder="Amount"></td>
      <td>
        <select class="form-control" id="edit-category">${categoryOptions}</select>
      </td>
      <td><input class="form-control" id="edit-date" type="date" value="${e.date}"></td>
      <td colspan="1"><input class="form-control" id="edit-notes" value="${escHtml(e.notes || '')}" placeholder="Notes"></td>
      <td>
        <div class="actions-cell">
          <button class="btn btn-sm btn-save" id="save-edit-btn">💾 Save</button>
          <button class="btn btn-sm btn-cancel" id="cancel-edit-btn">✕ Cancel</button>
        </div>
      </td>
    </tr>`;
}

/**
 * Update the four dashboard summary cards.
 * @param {object} s - Summary object from API
 */
function renderDashboardCards(s) {
  cardTotal.textContent      = `₹${Number(s.total || 0).toFixed(2)}`;
  cardCount.textContent      = s.count || 0;
  cardMonthTotal.textContent = `₹${Number(s.current_month_total || 0).toFixed(2)}`;
  cardMonthName.textContent  = s.current_month_name || '';

  // Trend chip
  const t = s.trend || {};
  const trendClass = { up: 'trend-up', down: 'trend-down', stable: 'trend-stable' }[t.trend] || 'trend-stable';
  cardTrend.innerHTML = `<span class="trend-chip ${trendClass}">${t.message || '—'}</span>`;
}

/**
 * Render the Monthly Budget KPI card with progress bar.
 * @param {number} budget   - User's set monthly budget (0 = not set)
 * @param {number} spent    - Amount spent this month
 */
function renderBudgetCard(budget, spent) {
  if (!cardBudget) return;
  if (!budget || budget <= 0) {
    cardBudget.textContent = 'Not set';
    cardBudgetMeta.textContent = 'Set your monthly limit';
    budgetSetRow.style.display = 'flex';
    budgetBarWrap.style.display = 'none';
    return;
  }

  const pct = Math.min((spent / budget) * 100, 100);
  const remaining = budget - spent;

  cardBudget.textContent = `₹${Number(budget).toFixed(0)}/mo`;
  cardBudgetMeta.textContent = remaining >= 0
    ? `₹${Math.abs(remaining).toFixed(2)} remaining`
    : `₹${Math.abs(remaining).toFixed(2)} over budget!`;

  // Show progress bar
  budgetSetRow.style.display = 'flex';
  budgetBarWrap.style.display = 'block';
  budgetBarFill.style.width = `${pct}%`;
  budgetBarFill.className = 'budget-bar-fill';
  if (pct >= 100) budgetBarFill.classList.add('danger');
  else if (pct >= 80) budgetBarFill.classList.add('warn');

  budgetBarSpent.textContent = `₹${spent.toFixed(2)} spent`;
  budgetBarLimit.textContent = `of ₹${budget.toFixed(0)}`;
}

/**
 * Update the Month-End Forecast KPI card (small card at top).
 * @param {object} f - Forecast object from API
 */
function renderForecastCard(f) {
  if (!cardForecast) return;
  const forecast = f.forecast_month_end || 0;
  const daily    = f.daily_avg || 0;

  cardForecast.textContent = forecast > 0 ? `₹${forecast.toFixed(2)}` : '₹0.00';
  cardForecastMeta.textContent = `₹${daily.toFixed(2)}/day avg · ${f.days_remaining} days left`;

  // Compare to budget if set
  if (currentBudget > 0) {
    const over = forecast > currentBudget;
    cardForecastBadge.innerHTML = over
      ? `<span class="trend-chip trend-up">⚠️ May exceed budget by ₹${(forecast - currentBudget).toFixed(2)}</span>`
      : `<span class="trend-chip trend-down">✅ Within budget (₹${(currentBudget - forecast).toFixed(2)} margin)</span>`;
  } else {
    cardForecastBadge.innerHTML = '';
  }
}

/**
 * Render the full Spending Forecast detail panel.
 * @param {object} f - Forecast object from API
 */
function renderForecastPanel(f) {
  if (!forecastDetail) return;

  // Confidence badge
  if (forecastConfBadge) {
    const confMap = { low: '🟡 Low Confidence', medium: '🔵 Medium Confidence', high: '🟢 High Confidence' };
    const confClass = { low: 'confidence-low', medium: 'confidence-medium', high: 'confidence-high' };
    forecastConfBadge.textContent = confMap[f.confidence] || '';
    forecastConfBadge.className = `forecast-confidence-badge ${confClass[f.confidence] || ''}`;
  }

  const budgetRow = currentBudget > 0
    ? `<div class="forecast-stat">
        <div class="forecast-stat-label">Budget vs Forecast</div>
        <div class="forecast-stat-value ${f.forecast_month_end > currentBudget ? 'danger' : 'accent'}">
          ${f.forecast_month_end > currentBudget ? '⚠️ Over' : '✅ Under'}
        </div>
        <div class="forecast-stat-sub">₹${Math.abs(currentBudget - f.forecast_month_end).toFixed(2)} ${f.forecast_month_end > currentBudget ? 'over' : 'under'} your ₹${currentBudget.toFixed(0)} budget</div>
      </div>`
    : '';

  forecastDetail.innerHTML = `
    <div class="forecast-stat">
      <div class="forecast-stat-label">Spent This Month</div>
      <div class="forecast-stat-value accent">₹${(f.current_month_total || 0).toFixed(2)}</div>
      <div class="forecast-stat-sub">${f.days_elapsed} of ${f.days_in_month} days elapsed</div>
    </div>
    <div class="forecast-stat">
      <div class="forecast-stat-label">Daily Average</div>
      <div class="forecast-stat-value">₹${(f.daily_avg || 0).toFixed(2)}</div>
      <div class="forecast-stat-sub">per day so far</div>
    </div>
    <div class="forecast-stat">
      <div class="forecast-stat-label">Days Remaining</div>
      <div class="forecast-stat-value indigo">${f.days_remaining}</div>
      <div class="forecast-stat-sub">out of ${f.days_in_month} in ${f.current_month_name}</div>
    </div>
    <div class="forecast-stat">
      <div class="forecast-stat-label">Projected Month Total</div>
      <div class="forecast-stat-value ${f.forecast_month_end > (currentBudget || Infinity) ? 'danger' : 'indigo'}">
        ₹${(f.forecast_month_end || 0).toFixed(2)}
      </div>
      <div class="forecast-stat-sub">at current daily rate</div>
    </div>
    ${budgetRow}
  `;
}

// ─────────────────────────────────────────────────────────────────────────────
// CHART RENDERERS
// ─────────────────────────────────────────────────────────────────────────────

/** Shared Chart.js defaults matching the dark theme */
const CHART_DEFAULTS = {
  colors: [
    '#00d4aa','#667eea','#f59e0b','#ef4444','#06b6d4',
    '#8b5cf6','#10b981','#f97316','#ec4899','#84cc16','#6366f1','#14b8a6',
  ],
  textColor: 'rgba(156,163,175,0.9)',
  gridColor: 'rgba(255,255,255,0.06)',
};

/**
 * Doughnut chart — spending by category.
 * @param {object} byCategory - { "Food & Dining": 430, ... }
 */
function renderCategoryChart(byCategory = {}) {
  const canvas = document.getElementById('category-chart');
  if (!canvas) return;

  const entries = Object.entries(byCategory).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return;

  const labels = entries.map(([cat]) => cat);
  const data   = entries.map(([, amt]) => amt);

  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: CHART_DEFAULTS.colors,
        borderColor: 'transparent',
        borderWidth: 0,
        hoverOffset: 8,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '62%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: CHART_DEFAULTS.textColor,
            font: { size: 11 },
            padding: 14,
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ₹${ctx.parsed.toFixed(2)} (${((ctx.parsed / data.reduce((a,b)=>a+b,0))*100).toFixed(1)}%)`,
          },
        },
      },
    },
  });
}

/**
 * Bar chart — monthly spending totals.
 * @param {object} monthly - { "2026-05": 540, ... }
 */
function renderMonthlyChart(monthly = {}) {
  const canvas = document.getElementById('monthly-chart');
  if (!canvas) return;

  // Show up to 6 months, oldest → newest (left → right)
  const entries = Object.entries(monthly).slice(0, 6).reverse();
  if (!entries.length) return;

  const labels = entries.map(([key]) => {
    const [yr, mo] = key.split('-');
    return new Date(+yr, +mo - 1, 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  });
  const data = entries.map(([, amt]) => amt);

  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Monthly Spend',
        data,
        backgroundColor: 'rgba(102,126,234,0.75)',
        borderColor: '#667eea',
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: ctx => ` ₹${ctx.parsed.y.toFixed(2)}` },
        },
      },
      scales: {
        x: {
          ticks: { color: CHART_DEFAULTS.textColor, font: { size: 11 } },
          grid:  { display: false },
        },
        y: {
          ticks: {
            color: CHART_DEFAULTS.textColor,
            font:  { size: 11 },
            callback: v => '₹' + v.toLocaleString(),
          },
          grid: { color: CHART_DEFAULTS.gridColor },
        },
      },
    },
  });
}

/**
 * Grouped bar chart — current spend vs projected end-of-month vs budget.
 * @param {object} f - Forecast object from API
 */
function renderForecastChart(f) {
  const canvas = document.getElementById('forecast-chart');
  if (!canvas) return;

  const current   = f.current_month_total  || 0;
  const projected = f.forecast_month_end   || 0;
  const label     = f.current_month_name   || 'This Month';

  const datasets = [
    {
      label: 'Spent So Far',
      data:  [current],
      backgroundColor: 'rgba(0,212,170,0.80)',
      borderColor:     '#00d4aa',
      borderWidth: 1,
      borderRadius: 6,
      borderSkipped: false,
    },
    {
      label: 'Projected Total',
      data:  [projected],
      backgroundColor: 'rgba(99,102,241,0.75)',
      borderColor:     '#6366f1',
      borderWidth: 1,
      borderRadius: 6,
      borderSkipped: false,
    },
  ];

  if (currentBudget > 0) {
    datasets.push({
      label: 'Monthly Budget',
      data:  [currentBudget],
      backgroundColor: 'rgba(245,158,11,0.55)',
      borderColor:     '#f59e0b',
      borderWidth: 2,
      borderRadius: 6,
      borderSkipped: false,
    });
  }

  if (forecastChart) forecastChart.destroy();
  forecastChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: [label],
      datasets,
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: CHART_DEFAULTS.textColor,
            font:  { size: 11 },
            padding: 16,
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ₹${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: CHART_DEFAULTS.textColor },
          grid:  { display: false },
        },
        y: {
          ticks: {
            color: CHART_DEFAULTS.textColor,
            font:  { size: 11 },
            callback: v => '₹' + v.toLocaleString(),
          },
          grid: { color: CHART_DEFAULTS.gridColor },
        },
      },
    },
  });
}

/**
 * Render per-category progress bars in the summary panel.
 * @param {object} byCategory - { "Food & Dining": 430.0, ... }
 * @param {number} total - Grand total for percentage calculation
 */
function renderCategoryBars(byCategory = {}, total = 0) {
  if (!Object.keys(byCategory).length) {
    categoryBars.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">No data yet.</p>';
    return;
  }
  const sorted = Object.entries(byCategory).sort((a, b) => b[1] - a[1]);
  categoryBars.innerHTML = sorted.map(([cat, amt]) => {
    const pct = total > 0 ? Math.min((amt / total) * 100, 100).toFixed(1) : 0;
    const meta = CATEGORY_META[cat] || CATEGORY_META['Other'];
    return `
      <div class="category-bar-item">
        <div class="category-bar-label">
          <span>${meta.icon} ${cat}</span>
          <span>₹${Number(amt).toFixed(2)} (${pct}%)</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${pct}%"></div>
        </div>
      </div>`;
  }).join('');
}

/**
 * Render the monthly spending list.
 * @param {object} monthly - { "2026-05": 540.0, ... }
 */
function renderMonthlyList(monthly = {}) {
  const entries = Object.entries(monthly);
  if (!entries.length) {
    monthlyList.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">No data yet.</p>';
    return;
  }
  monthlyList.innerHTML = entries.slice(0, 6).map(([key, amt]) => {
    const [yr, mo] = key.split('-');
    const name = new Date(+yr, +mo - 1, 1).toLocaleDateString('en-US', { month:'long', year:'numeric' });
    return `
      <div class="month-row">
        <span class="month-name">📅 ${name}</span>
        <span class="month-amount">₹${Number(amt).toFixed(2)}</span>
      </div>`;
  }).join('');
}

/**
 * Render budget alerts below the summary.
 * @param {Array} alerts
 */
function renderAlerts(alerts) {
  if (!alerts.length) {
    alertsContainer.innerHTML = '<p style="color:var(--text-muted);font-size:.82rem;">✅ All budgets are on track.</p>';
    return;
  }
  alertsContainer.innerHTML = alerts.map(a =>
    `<div class="alert alert-${a.level}">${a.message}</div>`
  ).join('');
}

// ─────────────────────────────────────────────────────────────────────────────
// FORM: ADD EXPENSE
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Handle the "Add Expense" form submission.
 * Sends POST /api/expenses and refreshes the UI on success.
 */
async function handleFormSubmit(e) {
  e.preventDefault();
  const submitBtn = document.getElementById('submit-btn');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Saving...';

  const payload = {
    title:    document.getElementById('expense-title').value.trim(),
    amount:   document.getElementById('expense-amount').value,
    category: document.getElementById('expense-category').value,
    date:     document.getElementById('expense-date').value,
    notes:    document.getElementById('expense-notes').value.trim(),
  };

  try {
    await apiFetch(`${API}/expenses`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    showToast('✅ Transaction logged successfully!', 'success');
    expenseForm.reset();
    document.getElementById('expense-date').valueAsDate = new Date();
    await loadExpenses();
    await loadSummary();
    await loadForecast();
  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '＋ Log Transaction';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// INLINE EDIT
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Switch a table row into inline edit mode.
 * @param {string} id - expense_id to edit
 */
function startEdit(id) {
  editingId = id;
  const expense = allExpenses.find(e => e.expense_id === id);
  if (!expense) return;

  const row = expenseTbody.querySelector(`tr[data-id="${id}"]`);
  if (!row) return;

  row.outerHTML = buildEditRow(expense);

  // Re-query after outerHTML replacement
  document.getElementById('save-edit-btn').addEventListener('click', saveEdit);
  document.getElementById('cancel-edit-btn').addEventListener('click', cancelEdit);
}

/**
 * Save the edited expense by calling PUT /api/expenses/:id
 */
async function saveEdit() {
  const payload = {
    title:    document.getElementById('edit-title').value.trim(),
    amount:   document.getElementById('edit-amount').value,
    category: document.getElementById('edit-category').value,
    date:     document.getElementById('edit-date').value,
    notes:    document.getElementById('edit-notes').value.trim(),
  };

  const saveBtn = document.getElementById('save-edit-btn');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    await apiFetch(`${API}/expenses/${editingId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    showToast('✅ Transaction updated!', 'success');
    editingId = null;
    await loadExpenses();
    await loadSummary();
    await loadForecast();
  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
    saveBtn.disabled = false;
    saveBtn.textContent = '💾 Save';
  }
}

/**
 * Cancel the inline edit and restore the original row.
 */
function cancelEdit() {
  editingId = null;
  renderTable(filteredExpenses);
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE
// ─────────────────────────────────────────────────────────────────────────────

function openDeleteModal(id) {
  deleteTargetId = id;
  deleteModal.classList.add('open');
}

function closeDeleteModal() {
  deleteTargetId = null;
  deleteModal.classList.remove('open');
}

async function confirmDelete() {
  if (!deleteTargetId) return;
  closeDeleteModal();

  try {
    await apiFetch(`${API}/expenses/${deleteTargetId}`, { method: 'DELETE' });
    showToast('🗑️ Transaction removed.', 'info');
    deleteTargetId = null;
    await loadExpenses();
    await loadSummary();
    await loadForecast();
  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// UI HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/** Show a loading indicator in the table while fetching. */
function showTableLoading() {
  expenseTbody.innerHTML = `
    <tr class="loading-row">
      <td colspan="7">
        <span class="spinner"></span>
        &nbsp;&nbsp;Loading transactions...
      </td>
    </tr>`;
}

/**
 * Display a toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 * @param {number} duration - ms before auto-dismiss
 */
function showToast(message, type = 'info', duration = 3500) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} str
 * @returns {string}
 */
function escHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(str || ''));
  return d.innerHTML;
}

/**
 * Format an ISO timestamp to a human-readable date-time string.
 * @param {string} isoStr
 * @returns {string}
 */
function formatTime(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr + 'Z').toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return isoStr; }
}
