import './Sidebar.css';

/**
 * Sidebar — session-aware research history list.
 *
 * Props:
 *  history      – array of { id, title, status }
 *                 Includes both live session tasks and mock demo entries.
 *  selectedId   – currently highlighted entry id
 *  onSelect     – (id) => void
 *  onNewResearch – () => void
 *  collapsed    – boolean
 *  onToggle     – () => void
 */
export default function Sidebar({
  history = [],
  selectedId,
  onSelect,
  onNewResearch,
  collapsed,
  onToggle,
}) {
  return (
    <>
      {/* Toggle button — visible only when sidebar is collapsed */}
      <button
        className={`sidebar-toggle ${collapsed ? '' : 'hidden'}`}
        onClick={onToggle}
        aria-label="Open sidebar"
      >
        ☰
      </button>

      <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        {/* ── Brand ─────────────────────────────────────── */}
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon" aria-hidden="true">R</div>
          <span className="sidebar-brand-text">ResearchAI</span>

          {/* Collapse button inside sidebar */}
          <button
            className="sidebar-toggle"
            onClick={onToggle}
            aria-label="Collapse sidebar"
            style={{
              position: 'static',
              marginLeft: 'auto',
              boxShadow: 'none',
              border: 'none',
              background: 'transparent',
              width: 28,
              height: 28,
              fontSize: 16,
            }}
          >
            ✕
          </button>
        </div>

        {/* ── New Research ──────────────────────────────── */}
        <button className="new-research-btn" onClick={onNewResearch}>
          <span aria-hidden="true">＋</span>
          New Research
        </button>

        {/* ── History ───────────────────────────────────── */}
        <p className="sidebar-section-title">Recent Research</p>

        {history.length === 0 ? (
          <p className="sidebar-empty">No research yet.</p>
        ) : (
          <ul className="history-list">
            {history.map((entry) => (
              <li key={entry.id}>
                <button
                  className={`history-item ${selectedId === entry.id ? 'active' : ''}`}
                  onClick={() => onSelect(entry.id)}
                  title={entry.title}
                >
                  {/* Running indicator dot */}
                  {entry.status === 'running' && (
                    <span className="history-running-dot" aria-label="Running" />
                  )}
                  {entry.title}
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* ── Settings ──────────────────────────────────── */}
        <div className="sidebar-footer">
          <button className="settings-btn">
            <span aria-hidden="true">⚙</span>
            Settings
          </button>
        </div>
      </aside>
    </>
  );
}
