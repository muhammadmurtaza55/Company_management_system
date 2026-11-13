/**
 * Company Management System - Main Interactive JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Bootstrap Tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map((el) => new bootstrap.Tooltip(el));

  // Initialize DB Test Button if present on page
  const testDbBtn = document.getElementById('btn-test-db');
  if (testDbBtn) {
    testDbBtn.addEventListener('click', runLiveDbTest);
  }

  // Initialize DB Create Tables Button if present
  const initDbBtn = document.getElementById('btn-init-db');
  if (initDbBtn) {
    initDbBtn.addEventListener('click', runInitDbTables);
  }
});

/**
 * Runs a live asynchronous test against /api/db-status
 */
async function runLiveDbTest() {
  const btn = document.getElementById('btn-test-db');
  const resultCard = document.getElementById('live-test-result');
  const spinner = document.getElementById('test-spinner');

  if (!btn) return;

  btn.disabled = true;
  if (spinner) spinner.classList.remove('d-none');

  try {
    const response = await fetch('/api/db-status');
    const data = await response.json();

    if (resultCard) {
      resultCard.classList.remove('d-none');
      const alertBox = resultCard.querySelector('.alert-content');
      
      if (data.connected) {
        alertBox.innerHTML = `
          <div class="alert alert-success d-flex align-items-center mb-0">
            <i class="bi bi-check-circle-fill fs-4 me-3 text-success"></i>
            <div>
              <h6 class="fw-bold mb-1">PostgreSQL Connected Successfully!</h6>
              <div class="small">Database: <strong>${data.database_name}</strong> | Latency: <strong>${data.latency_ms} ms</strong></div>
              <div class="small text-muted mt-1">${data.version || ''}</div>
            </div>
          </div>
        `;
      } else {
        alertBox.innerHTML = `
          <div class="alert alert-danger d-flex align-items-start mb-0">
            <i class="bi bi-exclamation-triangle-fill fs-4 me-3 text-danger mt-1"></i>
            <div>
              <h6 class="fw-bold mb-1">PostgreSQL Connection Test Failed</h6>
              <div class="small mb-1">${data.message || 'Unable to establish connection.'}</div>
              ${data.error ? `<pre class="bg-dark text-danger-emphasis p-2 rounded small mt-2 mb-0">${escapeHtml(data.error)}</pre>` : ''}
              ${data.hint ? `<div class="small text-warning-emphasis fw-semibold mt-2"><i class="bi bi-lightbulb me-1"></i>${escapeHtml(data.hint)}</div>` : ''}
            </div>
          </div>
        `;
      }
    }
  } catch (err) {
    if (resultCard) {
      resultCard.classList.remove('d-none');
      resultCard.querySelector('.alert-content').innerHTML = `
        <div class="alert alert-danger mb-0">
          <i class="bi bi-x-circle me-2"></i>Network request failed: ${escapeHtml(err.message)}
        </div>
      `;
    }
  } finally {
    btn.disabled = false;
    if (spinner) spinner.classList.add('d-none');
  }
}

/**
 * Calls /api/init-db to run db.create_all() on PostgreSQL
 */
async function runInitDbTables() {
  const btn = document.getElementById('btn-init-db');
  if (!btn) return;

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Creating Tables...`;

  try {
    const res = await fetch('/api/init-db', { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      alert(`Success: ${data.message}\nTables in PostgreSQL: ${data.tables.join(', ')}`);
      window.location.reload();
    } else {
      alert(`Failed to initialize tables:\n${data.message || data.error}`);
    }
  } catch (err) {
    alert(`Request error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-table me-1"></i> Initialize Database Tables`;
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

