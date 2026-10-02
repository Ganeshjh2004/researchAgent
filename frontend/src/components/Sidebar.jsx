import ThemeToggle from './ThemeToggle';
import './Sidebar.css';

/**
 * Sidebar — redesigned navigation rail with backend-backed research history
 * and persistent theme control.
 *
 * Props:
 *  history         – array of { id, title, status, error? }
 *  historyLoading  – boolean indicating backend history fetch
 *  historyError    – string | null
 *  onRetryHistory  – () => void
 *  selectedId      – string | null (active item)
 *  onSelect        – (id) => void
 *  onNewResearch   – () => void
 *  collapsed       – boolean
 *  onToggle        – () => void
 *  theme           – 'light' | 'dark'
 *  onToggleTheme   – () => void
 */
export default function Sidebar({
  history = [],
  historyLoading = false,
  historyError = null,
  onRetryHistory,
  selectedId,
  onSelect,
  onNewResearch,
  collapsed,
  onToggle,
  theme = 'light',
  onToggleTheme,
}) {
  return (
    <>
      {/* Mobile backdrop scrim to dismiss drawer on click */}
      {!collapsed && (
        <div
          className="sidebar-backdrop"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}

      <aside
        className={`sidebar ${collapsed ? 'collapsed' : ''}`}
        aria-label="Navigation & History Sidebar"
      >
        {/* ── Brand Header ────────────────────────────────────── */}
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
                <path d="M6 6h10" />
                <path d="M6 10h7" />
                <path d="m14 14 3 3 5-5" />
              </svg>
            </div>
            <div className="sidebar-brand-info">
              <span className="sidebar-brand-name">ResearchMate</span>
              <span className="sidebar-brand-tag">AI Assistant</span>
            </div>
          </div>

          {/* Close / Collapse button inside sidebar */}
          <button
            type="button"
            className="sidebar-close-btn"
            onClick={onToggle}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        {/* ── Action: New Research ────────────────────────────── */}
        <div className="sidebar-actions">
          <button
            type="button"
            className="new-research-btn"
            onClick={onNewResearch}
            aria-label="Start new research"
          >
            <svg
              className="action-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 5v14" />
              <path d="M5 12h14" />
            </svg>
            <span>New Research</span>
          </button>
        </div>

        {/* ── Research History List ───────────────────────────── */}
        <div className="sidebar-history-container">
          <div className="sidebar-section-header">
            <span className="sidebar-section-title">Research History</span>
            {history.length > 0 && (
              <span className="sidebar-count-badge">{history.length}</span>
            )}
          </div>

          <div className="sidebar-history-scroll" tabIndex={0} role="region" aria-label="Research history list">
            {historyLoading && history.length === 0 ? (
              <div className="sidebar-loading-state" aria-live="polite">
                <div className="history-skeleton" />
                <div className="history-skeleton short" />
                <div className="history-skeleton" />
              </div>
            ) : historyError && history.length === 0 ? (
              <div className="sidebar-error-state">
                <p className="sidebar-error-msg">{historyError}</p>
                {onRetryHistory && (
                  <button
                    type="button"
                    className="sidebar-retry-btn"
                    onClick={onRetryHistory}
                  >
                    Retry
                  </button>
                )}
              </div>
            ) : history.length === 0 ? (
              <div className="sidebar-empty-state">
                <p className="sidebar-empty-title">No past research</p>
                <p className="sidebar-empty-hint">
                  Your research queries and synthesized reports will be saved here.
                </p>
              </div>
            ) : (
              <ul className="history-list">
                {history.map((entry) => {
                  const isSelected = selectedId === entry.id;
                  const status = entry.status?.toLowerCase() || 'unknown';

                  return (
                    <li key={entry.id}>
                      <button
                        type="button"
                        className={`history-item ${isSelected ? 'active' : ''}`}
                        onClick={() => onSelect(entry.id)}
                        title={entry.title}
                        aria-current={isSelected ? 'true' : undefined}
                      >
                        <span
                          className={`history-status-dot status-${status}`}
                          title={`Status: ${status}`}
                          aria-label={`Status: ${status}`}
                        />
                        <span className="history-item-title">{entry.title}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* ── Footer: Theme & Controls ────────────────────────── */}
        <div className="sidebar-footer">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </aside>
    </>
  );
}
