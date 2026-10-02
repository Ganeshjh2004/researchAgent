import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getReportUrl } from '../services/researchApi';
import './ResearchResult.css';

/**
 * Extract clean domain name from URL string for source badges.
 */
function extractDomain(url) {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return 'web';
  }
}

/**
 * Calculate approximate word count for summary text.
 */
function getWordCount(text) {
  if (!text) return 0;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/**
 * ResearchResult (Research Workspace) — Dedicated workspace where users
 * monitor research progress and review structured findings, markdown summary,
 * citations, and download reports.
 *
 * Props:
 *  data          – result object or null
 *  loading       – boolean
 *  statusText    – string shown during progress
 *  error         – string or null
 *  activeQuery   – string (fallback title)
 *  taskId        – string (UUID)
 *  onNewResearch – () => void
 *  onRetry       – () => void
 */
export default function ResearchResult({
  data,
  loading = false,
  statusText = '',
  error = null,
  activeQuery = '',
  taskId = null,
  onNewResearch,
  onRetry,
}) {
  const [copied, setCopied] = useState(false);
  const [copiedId, setCopiedId] = useState(false);

  const displayQuery = data?.title ?? data?.query ?? activeQuery ?? 'Research Task';
  const effectiveId = data?.id ?? taskId;
  const isCompleted = data?.status?.toLowerCase() === 'completed';
  const isFailed = Boolean(error) || data?.status?.toLowerCase() === 'failed';
  const isQueued = !isCompleted && !isFailed && (data?.status?.toLowerCase() === 'queued' || statusText.toLowerCase().includes('queued'));

  // Report download URL
  const reportUrl = (data?.filename && effectiveId) || (isCompleted && effectiveId)
    ? getReportUrl(effectiveId)
    : null;

  // Detect whether summary preview was truncated by worker
  const summaryIsTruncated = data?.summary && data.summary.endsWith('...');
  const wordCount = getWordCount(data?.summary);

  // Clipboard copy handler for markdown content
  const handleCopySummary = async () => {
    if (!data?.summary) return;
    try {
      await navigator.clipboard.writeText(data.summary);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  // Clipboard copy handler for task ID
  const handleCopyTaskId = async () => {
    if (!effectiveId) return;
    try {
      await navigator.clipboard.writeText(effectiveId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch {
      // Fallback
    }
  };

  // Safe report download via Blob to respect Content-Disposition filename in all browsers
  const handleDownload = async (e) => {
    e.preventDefault();
    if (!reportUrl) return;
    try {
      const res = await fetch(reportUrl);
      if (!res.ok) throw new Error("Failed to fetch report");
      
      const blob = await res.blob();
      let filename = data?.filename || `research_report_${effectiveId}.txt`;
      
      const disposition = res.headers.get('Content-Disposition');
      if (disposition && disposition.indexOf('filename=') !== -1) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) {
          filename = match[1];
        }
      }
      
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Download failed:", err);
      window.open(reportUrl, '_blank'); // fallback
    }
  };

  return (
    <div className="workspace-wrapper">
      <div className="workspace-content">
        {/* ── Top Workspace Header ────────────────────────────── */}
        <header className="workspace-header">
          <div className="workspace-header-main">
            <button
              type="button"
              className="workspace-back-btn"
              onClick={onNewResearch}
              aria-label="Back to research home"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              <span>All Research</span>
            </button>

            <h1 className="workspace-title">{displayQuery}</h1>

            <div className="workspace-meta-row">
              {/* Status Badge */}
              <div className="workspace-status-badge">
                {loading ? (
                  <span className={`status-pill ${isQueued ? 'status-queued' : 'status-running'}`}>
                    <span className="status-indicator-dot" />
                    <span>{isQueued ? 'Queued' : 'Researching'}</span>
                  </span>
                ) : isCompleted ? (
                  <span className="status-pill status-completed">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="status-icon">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Completed</span>
                  </span>
                ) : isFailed ? (
                  <span className="status-pill status-failed">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="status-icon">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                    <span>Failed</span>
                  </span>
                ) : (
                  <span className="status-pill status-neutral">
                    <span>{data?.status ?? 'Unknown'}</span>
                  </span>
                )}
              </div>

              {/* Task ID copy pill */}
              {effectiveId && (
                <button
                  type="button"
                  className="workspace-id-badge"
                  onClick={handleCopyTaskId}
                  title="Click to copy Task ID"
                  aria-label={`Task ID: ${effectiveId}`}
                >
                  <span className="id-label">ID:</span>
                  <span className="id-value">{effectiveId.slice(0, 8)}…</span>
                  <span className="id-copy-hint">{copiedId ? '✓' : 'Copy'}</span>
                </button>
              )}
            </div>
          </div>

          <div className="workspace-header-actions">
            {isCompleted && data?.summary && (
              <button
                type="button"
                className="workspace-action-btn secondary"
                onClick={handleCopySummary}
                aria-label="Copy markdown summary"
              >
                {copied ? (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="btn-icon">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                    <span>Copy Markdown</span>
                  </>
                )}
              </button>
            )}

            {isCompleted && reportUrl && (
              <a
                href={reportUrl}
                onClick={handleDownload}
                target="_blank"
                rel="noopener noreferrer"
                className="workspace-action-btn primary"
                aria-label="Download full compiled report"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="btn-icon">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                <span>Download Report</span>
              </a>
            )}

            <button
              type="button"
              className="workspace-action-btn ghost"
              onClick={onNewResearch}
              aria-label="Start new research"
            >
              <span>+ New</span>
            </button>
          </div>
        </header>

        {/* ── State 1: Loading & In-Flight State ───────────────── */}
        {loading && (
          <section className="workspace-running-state" aria-live="polite">
            <div className="running-banner">
              <span className="running-spinner" aria-hidden="true" />
              <div className="running-text">
                <p className="running-status-title">
                  {statusText || 'Synthesizing research…'}
                </p>
                <p className="running-status-subtitle">
                  LangGraph agent is querying Wikipedia and DuckDuckGo, evaluating factual grounding, and compiling structured findings.
                </p>
              </div>
            </div>

            {/* Bento Shimmer Skeleton */}
            <div className="workspace-bento-grid skeleton-active">
              <div className="bento-card bento-summary">
                <div className="skeleton-line title" />
                <div className="skeleton-line" />
                <div className="skeleton-line" />
                <div className="skeleton-line short" />
                <div className="skeleton-line" />
                <div className="skeleton-line" />
              </div>
              <div className="bento-sidebar-stack">
                <div className="bento-card bento-sources">
                  <div className="skeleton-line title" />
                  <div className="skeleton-card" />
                  <div className="skeleton-card" />
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── State 2: Error & Failed State ───────────────────── */}
        {!loading && (isFailed || error) && (
          <section className="workspace-error-card" role="alert">
            <div className="error-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <div className="error-card-content">
              <h2 className="error-card-title">Research Task Failed</h2>
              <p className="error-card-message">
                {error || data?.error || 'The research workflow encountered an unrecoverable failure during execution.'}
              </p>
              <div className="error-card-actions">
                <button
                  type="button"
                  className="error-retry-btn"
                  onClick={onRetry || onNewResearch}
                >
                  Start New Research
                </button>
              </div>
            </div>
          </section>
        )}

        {/* ── State 3: Completed Bento-Grid Workspace ─────────── */}
        {!loading && !isFailed && !error && data && (
          <div className="workspace-bento-grid">
            {/* ── Left / Main Column: Executive Summary ────────── */}
            <article className="bento-card bento-summary">
              <div className="bento-card-header">
                <div className="bento-card-title-group">
                  <h2 className="bento-card-title">
                    {summaryIsTruncated ? 'Executive Summary Preview' : 'Executive Summary'}
                  </h2>
                  {wordCount > 0 && (
                    <span className="summary-word-badge">~{wordCount} words</span>
                  )}
                </div>

                {reportUrl && (
                  <a
                    href={reportUrl}
                    onClick={handleDownload}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="card-quick-download"
                    title="Download full text report"
                  >
                    ↓ Full Report
                  </a>
                )}
              </div>

              {/* Summary Truncation Banner */}
              {summaryIsTruncated && reportUrl && (
                <div className="truncation-alert">
                  <span className="truncation-icon" aria-hidden="true">ℹ</span>
                  <span>
                    Summary preview shows first ~300 lines.{' '}
                    <a href={reportUrl} onClick={handleDownload} target="_blank" rel="noopener noreferrer">
                      Download the complete compiled report
                    </a>{' '}
                    for full text and data.
                  </span>
                </div>
              )}

              {/* Markdown Content */}
              {data.summary ? (
                <div className="summary-markdown-body">
                  <ReactMarkdown>{data.summary}</ReactMarkdown>
                </div>
              ) : (
                <div className="summary-fallback-notice">
                  <p className="fallback-headline">Summary Preview Unavailable in Cache</p>
                  <p className="fallback-text">
                    This completed historical record was retrieved from persistent database storage where live text previews are not cached.
                  </p>
                  {reportUrl ? (
                    <a
                      href={reportUrl}
                      onClick={handleDownload}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="fallback-download-btn"
                    >
                      ↓ Download Complete Research Report (.txt)
                    </a>
                  ) : (
                    <p className="fallback-missing">No report file was recorded for this task.</p>
                  )}
                </div>
              )}
            </article>

            {/* ── Right Column: Sources & Task Metadata ────────── */}
            <aside className="bento-sidebar-stack">
              {/* Sources Bento Card */}
              <section className="bento-card bento-sources">
                <div className="bento-card-header">
                  <div className="bento-card-title-group">
                    <h2 className="bento-card-title">Sources & Citations</h2>
                    <span className="sources-count-badge">
                      {data.sources?.length ?? 0}
                    </span>
                  </div>
                </div>

                {data.sources && data.sources.length > 0 ? (
                  <ul className="sources-list">
                    {data.sources.map((src, idx) => {
                      const name = typeof src === 'string' ? src : src.name;
                      const url = typeof src === 'object' && src !== null ? src.url : null;
                      const isValidUrl = url && (url.startsWith('http://') || url.startsWith('https://'));
                      const domain = isValidUrl ? extractDomain(url) : 'reference';

                      return (
                        <li key={idx} className="source-list-item">
                          {isValidUrl ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="source-card-link"
                              title={url}
                            >
                              <div className="source-domain-tag">{domain}</div>
                              <span className="source-name">{name}</span>
                              <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                className="source-external-icon"
                                aria-hidden="true"
                              >
                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                <polyline points="15 3 21 3 21 9" />
                                <line x1="10" y1="14" x2="21" y2="3" />
                              </svg>
                            </a>
                          ) : (
                            <div className="source-card-plain">
                              <div className="source-domain-tag">info</div>
                              <span className="source-name">{name}</span>
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="sources-empty-notice">
                    No web citation links were returned for this task.
                  </p>
                )}
              </section>

              {/* Task Details Bento Card */}
              <section className="bento-card bento-details">
                <div className="bento-card-header">
                  <h3 className="bento-card-title">Artifact Details</h3>
                </div>

                <dl className="details-list">
                  <div className="details-row">
                    <dt className="details-label">Status</dt>
                    <dd className="details-value status-text-success">Verified Complete</dd>
                  </div>
                  {data.filename && (
                    <div className="details-row">
                      <dt className="details-label">Report File</dt>
                      <dd className="details-value mono" title={data.filename}>
                        {data.filename}
                      </dd>
                    </div>
                  )}
                  {effectiveId && (
                    <div className="details-row">
                      <dt className="details-label">Task UUID</dt>
                      <dd className="details-value mono" title={effectiveId}>
                        {effectiveId}
                      </dd>
                    </div>
                  )}
                </dl>
              </section>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
