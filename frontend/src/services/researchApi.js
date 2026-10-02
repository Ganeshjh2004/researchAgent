/**
 * researchApi.js
 *
 * Thin service module for all backend communication.
 * All components import from here — the base URL is never repeated elsewhere.
 *
 * Verified API contracts (from api.py):
 *
 *  POST  /api/v1/research
 *    Body:     { query: string }          (min 3, max 500 chars)
 *    Response: { task_id, status, query }  status = "queued"
 *
 *  GET   /api/v1/research/:taskId
 *    Response: { task_id, status, query, error? }
 *    Statuses: "queued" | "running" | "completed" | "failed"
 *
 *  GET   /api/v1/research/:taskId/result
 *    Response: { task_id, status, query, filename?, summary?, sources[], error? }
 *
 *  GET   /api/v1/research/:taskId/report
 *    Response: text/plain file download
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// ── Helpers ──────────────────────────────────────────────────────────────────

async function handleResponse(res) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // non-JSON error body — keep the HTTP status text
    }
    throw new Error(detail);
  }
  return res.json();
}

// ── Exported API calls ────────────────────────────────────────────────────────

/**
 * Submit a new research query.
 * @param {string} query
 * @returns {Promise<{ task_id: string, status: string, query: string }>}
 */
export async function submitResearch(query) {
  const res = await fetch(`${BASE_URL}/api/v1/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return handleResponse(res);
}

/**
 * Poll task status.
 * @param {string} taskId
 * @returns {Promise<{ task_id: string, status: string, query: string, error?: string }>}
 */
export async function getTaskStatus(taskId) {
  const res = await fetch(`${BASE_URL}/api/v1/research/${taskId}`);
  return handleResponse(res);
}

/**
 * Fetch full research result (only call when status === "completed").
 * @param {string} taskId
 * @returns {Promise<{ task_id: string, status: string, query: string, filename?: string, summary?: string, sources: string[], error?: string }>}
 */
export async function getTaskResult(taskId) {
  const res = await fetch(`${BASE_URL}/api/v1/research/${taskId}/result`);
  return handleResponse(res);
}

/**
 * Return the URL for the report download link.
 * The backend serves GET /api/v1/research/:taskId/report as a text/plain FileResponse.
 * We return the URL so the UI can open it in a new tab or trigger a download anchor.
 * @param {string} taskId
 * @returns {string}
 */
export function getReportUrl(taskId) {
  return `${BASE_URL}/api/v1/research/${taskId}/report`;
}

/**
 * Retrieve database-backed research history from the backend.
 * @param {number} [limit=50]
 * @param {number} [offset=0]
 * @returns {Promise<Array<{ task_id: string, status: string, query: string, error?: string }>>}
 */
export async function getTaskHistory(limit = 50, offset = 0) {
  const res = await fetch(`${BASE_URL}/api/v1/research/history?limit=${limit}&offset=${offset}`);
  return handleResponse(res);
}
