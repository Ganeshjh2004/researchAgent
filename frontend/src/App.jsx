import { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ResearchInput from './components/ResearchInput';
import ResearchResult from './components/ResearchResult';
import {
  submitResearch,
  getTaskStatus,
  getTaskResult,
  getTaskHistory,
} from './services/researchApi';
import './App.css';

/**
 * Polling interval in ms. The backend worker may take tens of seconds for a
 * real LangGraph run, so 2 s is a reasonable balance between responsiveness
 * and server load.
 */
const POLL_INTERVAL_MS = 2000;

/**
 * Maximum time (ms) to wait for a task to complete before giving up.
 * Real research runs can take 60–120 s depending on the model/tools.
 */
const POLL_TIMEOUT_MS = 180_000; // 3 minutes

export default function App() {
  // ── Theme State ───────────────────────────────────────────────────────────
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('researchmate_theme');
      if (saved === 'dark' || saved === 'light') return saved;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch {
      return 'light';
    }
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('researchmate_theme', theme);
    } catch {
      // Ignore localStorage write failures in sandboxed environments
    }
  }, [theme]);

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  // ── Sidebar & History State ───────────────────────────────────────────────
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // ── Active Task State ─────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [activeResult, setActiveResult] = useState(null); // live result from backend
  const [error, setError] = useState(null);
  const [activeQuery, setActiveQuery] = useState('');

  // Ref for cleanup — stores the polling interval id
  const pollRef = useRef(null);
  // Ref for timeout guard
  const timeoutRef = useRef(null);

  // ── Stop Polling Helper ───────────────────────────────────────────────────
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  // Clean up on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  // ── Fetch Backend History on Initialization ───────────────────────────────
  const loadHistory = useCallback(async () => {
    setHistoryError(null);
    try {
      const records = await getTaskHistory(50, 0);
      const formatted = records.map((r) => ({
        id: r.task_id,
        title: r.query,
        status: r.status,
        error: r.error ?? null,
      }));

      setHistory((prev) => {
        // Keep any active in-flight running or queued tasks
        const inFlight = prev.filter((p) => p.status === 'running' || p.status === 'queued');
        const inFlightIds = new Set(inFlight.map((item) => item.id));
        const deduplicated = formatted.filter((item) => !inFlightIds.has(item.id));
        return [...inFlight, ...deduplicated];
      });
    } catch (err) {
      setHistoryError(err.message || 'Unable to connect to backend history.');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleRetryHistory = useCallback(() => {
    setHistoryLoading(true);
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const records = await getTaskHistory(50, 0);
        if (!ignore) {
          const formatted = records.map((r) => ({
            id: r.task_id,
            title: r.query,
            status: r.status,
            error: r.error ?? null,
          }));
          setHistory(formatted);
          setHistoryError(null);
        }
      } catch (err) {
        if (!ignore) {
          setHistoryError(err.message || 'Unable to connect to backend history.');
        }
      } finally {
        if (!ignore) {
          setHistoryLoading(false);
        }
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, []);

  // ── Result Fetching After Task Completion ─────────────────────────────────
  const fetchAndDisplayResult = useCallback(async (taskId, query) => {
    try {
      const result = await getTaskResult(taskId);
      const entry = {
        id: taskId,
        title: query,
        status: 'completed',
        summary: result.summary ?? (result.filename ? 'Full report is available for download below.' : '(No summary returned by backend)'),
        sources: result.sources ?? [],
        filename: result.filename ?? null,
      };
      setActiveResult(entry);

      // Add or update in session history
      setHistory((prev) => {
        const exists = prev.some((h) => h.id === taskId);
        if (exists) return prev.map((h) => (h.id === taskId ? entry : h));
        return [entry, ...prev];
      });
      setSelectedId(taskId);
    } catch (err) {
      setError(`Research completed but result could not be loaded: ${err.message}`);
    } finally {
      setLoading(false);
      setStatusText('');
    }
  }, []);

  // ── Polling Logic ─────────────────────────────────────────────────────────
  const startPolling = useCallback(
    (taskId, query) => {
      stopPolling();

      // Timeout guard — stop polling after POLL_TIMEOUT_MS
      timeoutRef.current = setTimeout(() => {
        stopPolling();
        setLoading(false);
        setStatusText('');
        setError('Research timed out. The backend may still be processing — try refreshing later.');
      }, POLL_TIMEOUT_MS);

      pollRef.current = setInterval(async () => {
        try {
          const data = await getTaskStatus(taskId);

          if (data.status === 'completed') {
            stopPolling();
            setStatusText('Finalising results…');
            await fetchAndDisplayResult(taskId, query);
          } else if (data.status === 'failed') {
            stopPolling();
            setLoading(false);
            setStatusText('');
            setError(data.error ?? 'Research task failed on the backend.');
          } else {
            // queued | running
            const label = data.status === 'running' ? 'Running research…' : 'Queued, waiting for worker…';
            setStatusText(label);
          }
        } catch {
          // Network error during poll — don't stop, keep trying (may be transient)
          setStatusText('Checking status… (connection issue, retrying)');
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling, fetchAndDisplayResult],
  );

  // ── Submit Handler ────────────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (query) => {
      stopPolling();
      setError(null);
      setActiveResult(null);
      setSelectedId(null);
      setActiveQuery(query);
      setLoading(true);
      setStatusText('Submitting query…');

      try {
        const data = await submitResearch(query);
        const taskId = data.task_id;

        // Add a provisional history entry so the sidebar displays it immediately
        const provisional = { id: taskId, title: query, status: 'running' };
        setHistory((prev) => [provisional, ...prev]);
        setSelectedId(taskId);

        setStatusText('Queued, waiting for worker…');
        startPolling(taskId, query);
      } catch (err) {
        setLoading(false);
        setStatusText('');
        setError(
          err.message.includes('Failed to fetch')
            ? 'Cannot reach the backend. Is the API server running on port 8000?'
            : `Submission failed: ${err.message}`,
        );
      }
    },
    [stopPolling, startPolling],
  );

  // ── New Research Handler ──────────────────────────────────────────────────
  const handleNewResearch = useCallback(() => {
    stopPolling();
    setSelectedId(null);
    setActiveResult(null);
    setActiveQuery('');
    setLoading(false);
    setStatusText('');
    setError(null);
    // On mobile screens, auto-close sidebar when clicking New Research
    if (window.innerWidth <= 768) {
      setSidebarCollapsed(true);
    }
  }, [stopPolling]);

  // ── History Item Click Handler ────────────────────────────────────────────
  const handleSelect = useCallback(
    async (id) => {
      const entry = history.find((h) => h.id === id);
      if (!entry) return;

      // If already active, no reload needed
      if (selectedId === id && activeResult && activeResult.id === id) {
        if (window.innerWidth <= 768) setSidebarCollapsed(true);
        return;
      }

      setSelectedId(id);
      setActiveQuery(entry.title);
      setError(null);

      // On mobile screens, auto-close sidebar after selection
      if (window.innerWidth <= 768) {
        setSidebarCollapsed(true);
      }

      // If task is actively running/queued, let polling proceed
      if (entry.status === 'running' || entry.status === 'queued') {
        return;
      }

      // If entry already has summary loaded in session memory
      if (entry.status === 'completed' && entry.summary !== undefined) {
        stopPolling();
        setLoading(false);
        setStatusText('');
        setActiveResult(entry);
        return;
      }

      // If task is recorded as failed in backend history
      if (entry.status === 'failed') {
        stopPolling();
        setLoading(false);
        setStatusText('');
        setActiveResult(null);
        setError(entry.error || 'This research task failed on the backend.');
        return;
      }

      // Completed historical task without summary cached in memory — fetch from backend
      stopPolling();
      setLoading(true);
      setStatusText('Loading research details…');

      try {
        const result = await getTaskResult(id);
        const fullEntry = {
          id: id,
          title: entry.title,
          status: result.status,
          summary: result.summary ?? (result.filename ? 'Full report is available for download below.' : '(No summary returned by backend)'),
          sources: result.sources ?? [],
          filename: result.filename ?? null,
          error: result.error ?? null,
        };

        // Cache in history list
        setHistory((prev) => prev.map((h) => (h.id === id ? { ...h, ...fullEntry } : h)));
        setActiveResult(fullEntry);
      } catch (err) {
        setError(`Could not load task details: ${err.message}`);
      } finally {
        setLoading(false);
        setStatusText('');
      }
    },
    [history, selectedId, activeResult, stopPolling],
  );

  // ── Render Application Shell ──────────────────────────────────────────────
  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <Sidebar
        history={history}
        historyLoading={historyLoading}
        historyError={historyError}
        onRetryHistory={handleRetryHistory}
        selectedId={selectedId}
        onSelect={handleSelect}
        onNewResearch={handleNewResearch}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      {/* Main Workspace Region */}
      <div className={`main-workspace ${sidebarCollapsed ? 'expanded' : ''}`}>
        {/* Top Application Bar (Header) */}
        <header className="app-topbar">
          <button
            type="button"
            className="topbar-toggle-btn"
            onClick={() => setSidebarCollapsed((c) => !c)}
            aria-label={sidebarCollapsed ? 'Open navigation sidebar' : 'Close navigation sidebar'}
            title={sidebarCollapsed ? 'Open sidebar' : 'Close sidebar'}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>

          <div className="topbar-brand">
            <span className="topbar-brand-title">ResearchMate</span>
          </div>

          <div className="topbar-actions">
            <button
              type="button"
              className="topbar-new-btn"
              onClick={handleNewResearch}
              aria-label="Start new research"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
              <span>New</span>
            </button>
          </div>
        </header>

        {/* Content Pane */}
        <main className="content-pane" id="main-content">
          {loading || activeResult || error ? (
            <ResearchResult
              data={activeResult}
              loading={loading}
              statusText={statusText}
              error={error}
              activeQuery={activeQuery || activeResult?.title || activeResult?.query}
              taskId={selectedId || activeResult?.id}
              onNewResearch={handleNewResearch}
              onRetry={handleNewResearch}
            />
          ) : (
            <ResearchInput onSubmit={handleSubmit} disabled={loading} />
          )}
        </main>
      </div>
    </div>
  );
}
