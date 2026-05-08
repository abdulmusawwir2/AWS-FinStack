/**
 * script.js - Expense Tracker Frontend Logic
 *
 * This file handles all client-side interactions:
 *  - Fetching expenses and summary from the Flask API
 *  - Rendering the expense table and dashboard cards
 *  - Add / Edit / Delete expense operations
 *  - Filtering by category and month
 *  - Toast notifications and modal confirmations
 *
 * API Base URL: /api  (same origin as Flask server)
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

// ─── Initialization ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Show today's date in the navbar
  document.getElementById('current-date').textContent =
    new Date().toLocaleDateString('en-US', { weekday:'long', year:'numeric', month:'long', day:'numeric' });

  // Default form date to today
  document.getElementById('expense-date').valueAsDate = new Date();

  // Load data
  loadExpenses();
  loadSummary();

  // Form submit
  expenseForm.addEventListener('submit', handleFormSubmit);

  // Filter listeners
  filterCategory.addEventListener('change', applyFilters);
  filterMonth.addEventListener('change', applyFilters);

  // Modal buttons
  deleteConfirmBtn.addEventListener('click', confirmDelete);
  deleteCancelBtn.addEventListener('click', closeDeleteModal);
  deleteModal.addEventListener('click', (e) => { if (e.target === deleteModal) closeDeleteModal(); });
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
    showToast(`Failed to load expenses: ${err.message}`, 'error');
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
    renderMonthlyList(s.monthly);
    renderAlerts(s.alerts || []);
  } catch (err) {
    showToast(`Failed to load summary: ${err.message}`, 'error');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER FUNCTIONS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Apply category and month filters then re-render the table.
 */
function applyFilters() {
  const cat   = filterCategory.value.toLowerCase();
  const month = filterMonth.value;  // "YYYY-MM" or ""

  filteredExpenses = allExpenses.filter(e => {
    const matchCat   = !cat   || e.category.toLowerCase() === cat;
    const matchMonth = !month || (e.date || '').startsWith(month);
    return matchCat && matchMonth;
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
          <div class="empty-icon">💸</div>
          <p>No expenses found. Add your first expense!</p>
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
        <div class="expense-title">${escHtml(e.title)}</div>
        ${e.notes ? `<div class="expense-notes">${escHtml(e.notes)}</div>` : ''}
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
          <button class="btn btn-sm btn-delete btn-delete-row" data-id="${e.expense_id}" title="Delete">🗑️ Delete</button>
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

  // Trend badge
  const t = s.trend || {};
  const trendClass = { up: 'trend-up', down: 'trend-down', stable: 'trend-stable' }[t.trend] || 'trend-stable';
  cardTrend.innerHTML = `<span class="trend-badge ${trendClass}">${t.message || '—'}</span>`;
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
    showToast('✅ Expense added successfully!', 'success');
    expenseForm.reset();
    document.getElementById('expense-date').valueAsDate = new Date();
    await loadExpenses();
    await loadSummary();
  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '➕ Add Expense';
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
    showToast('✅ Expense updated!', 'success');
    editingId = null;
    await loadExpenses();
    await loadSummary();
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
    showToast('🗑️ Expense deleted.', 'info');
    deleteTargetId = null;
    await loadExpenses();
    await loadSummary();
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
        &nbsp;&nbsp;Loading expenses...
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
