import ReactMarkdown from 'react-markdown';
import './ResearchResult.css';

/**
 * ResearchResult — renders loading, error, or completed research output.
 *
 * Props:
 *  data        – result object or null
 *  loading     – boolean
 *  statusText  – string shown below the spinner during loading
 *  error       – string or null
 *  onRetry     – () => void — called when the user clicks "Start New Research"
 *
 * Real result shape (from GET /api/v1/research/:id/result):
 *  { id, title (query), status, summary?, sources[], filename? }
 *
 * IMPORTANT — summary truncation:
 *  The backend worker stores only the first ~300 lines of the report as a preview.
 *  The full report is available exclusively via the /report download endpoint.
 *  This is a backend contract — the frontend labels this accurately.
 *
 * Note: keyFindings is NOT returned by the backend. It is present only in the
 * local mock data (data/mockData.js) and rendered when available.
 */
export default function ResearchResult({ data, loading, statusText, error, onRetry }) {

  // ── Loading state ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="loading-wrapper">
        <div className="loading-spinner" aria-hidden="true" />
        <p className="loading-text">
          {statusText || 'Researching… this may take a moment.'}
        </p>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="error-wrapper">
        <div className="error-icon" aria-hidden="true">⚠</div>
        <p className="error-title">Something went wrong</p>
        <p className="error-message">{error}</p>
        {onRetry && (
          <button className="error-retry-btn" onClick={onRetry}>
            Start New Research
          </button>
        )}
      </div>
    );
  }

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!data) return null;

  const isCompleted = data.status === 'completed' || data.status === 'Completed';
  const badgeClass = isCompleted ? 'completed' : 'in-progress';
  const badgeLabel = isCompleted ? 'Completed' : data.status ?? 'Unknown';

  // Report download URL — only meaningful when filename is set
  const reportUrl = data.filename && data.id
    ? `${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}/api/v1/research/${data.id}/report`
    : null;

  // The summary field is a ~300 line preview from the backend (worker.py).
  // Detect whether it was truncated by the backend's own "..." suffix logic.
  const summaryIsTruncated = data.summary && data.summary.endsWith('...');

  return (
    <div className="result-wrapper">
      <article className="result-content">

        {/* ── Header ─────────────────────────────────────── */}
        <header className="result-header">
          <h1 className="result-title">{data.title ?? data.query ?? 'Research Result'}</h1>
          <div className="result-header-row">
            <span className={`result-badge ${badgeClass}`}>{badgeLabel}</span>

            {/* Report download — only when backend returned a filename */}
            {reportUrl && (
              <a
                href={reportUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="report-download-link"
                aria-label="Download full research report"
              >
                ↓ Download Full Report
              </a>
            )}
          </div>
        </header>

        {/* ── Summary Preview ─────────────────────────────── */}
        {data.summary && (
          <section className="result-section">
            <div className="result-section-header">
              <h2 className="result-section-title">
                {summaryIsTruncated ? 'Summary Preview' : 'Summary'}
              </h2>
            </div>
            {/* Render Markdown as React components — no dangerouslySetInnerHTML */}
            <div className="result-markdown">
              <ReactMarkdown>{data.summary}</ReactMarkdown>
              {summaryIsTruncated && reportUrl && (
                <p className="result-inline-download">
                  For the full report, <a href={reportUrl} target="_blank" rel="noopener noreferrer">download it here</a>.
                </p>
              )}
            </div>
          </section>
        )}

        {/* ── Key Findings (mock data only — not in backend response) ─── */}
        {data.keyFindings && data.keyFindings.length > 0 && (
          <section className="result-section">
            <h2 className="result-section-title">Key Findings</h2>
            <ul className="result-findings">
              {data.keyFindings.map((finding, i) => (
                <li key={i}>{finding}</li>
              ))}
            </ul>
          </section>
        )}

        {/* ── Sources ─────────────────────────────────────── */}
        {data.sources && data.sources.length > 0 && (
          <section className="result-section">
            <h2 className="result-section-title">Sources</h2>
            <ul className="result-sources">
              {data.sources.map((src, i) => {
                const name = typeof src === 'string' ? src : src.name;
                const url = typeof src === 'object' && src !== null ? src.url : null;
                
                // Only render as link if it's a valid HTTP/HTTPS URL
                const isValidUrl = url && (url.startsWith('http://') || url.startsWith('https://'));

                return (
                  <li key={i}>
                    {isValidUrl ? (
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {name}
                      </a>
                    ) : (
                      <span>{name}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Fallback when no content is available */}
        {!data.summary && (!data.sources || data.sources.length === 0) && (
          <p className="result-empty-notice">
            No result content is available for this task yet.
          </p>
        )}

      </article>
    </div>
  );
}
