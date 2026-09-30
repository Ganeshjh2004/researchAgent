import { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ResearchInput from './components/ResearchInput';
import ResearchResult from './components/ResearchResult';
import { mockResearchEntries } from './data/mockData';
import { submitResearch, getTaskStatus, getTaskResult } from './services/researchApi';
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
  // ── Sidebar / history state ───────────────────────────────────────────────
  // session history: array of { id (task_id), title (query), result? }
  const [history, setHistory] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // ── Active task state ─────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [activeResult, setActiveResult] = useState(null); // live result from backend
  const [error, setError] = useState(null);

  // Ref for cleanup — stores the polling interval id
  const pollRef = useRef(null);
  // Ref for timeout guard
  const timeoutRef = useRef(null);

  // ── Stop polling helper ───────────────────────────────────────────────────
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

  // ── Result fetching after completion ─────────────────────────────────────
  const fetchAndDisplayResult = useCallback(async (taskId, query) => {
    try {
      const result = await getTaskResult(taskId);
      const entry = {
        id: taskId,
        title: query,
        status: 'completed',
        summary: result.summary ?? '(No summary returned by backend)',
        sources: result.sources ?? [],
        filename: result.filename ?? null,
        // keyFindings is not part of the backend response — omitted intentionally
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

  // ── Polling logic ─────────────────────────────────────────────────────────
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
        } catch (err) {
          // Network error during poll — don't stop, keep trying (may be transient)
          setStatusText('Checking status… (connection issue, retrying)');
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling, fetchAndDisplayResult],
  );

  // ── Submit handler ────────────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (query) => {
      stopPolling();
      setError(null);
      setActiveResult(null);
      setSelectedId(null);
      setLoading(true);
      setStatusText('Submitting query…');

      try {
        const data = await submitResearch(query);
        const taskId = data.task_id;

        // Add a provisional history entry so the sidebar shows it immediately
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

  // ── New Research handler ──────────────────────────────────────────────────
  const handleNewResearch = useCallback(() => {
    stopPolling();
    setSelectedId(null);
    setActiveResult(null);
    setLoading(false);
    setStatusText('');
    setError(null);
  }, [stopPolling]);

  // ── History item click handler ────────────────────────────────────────────
  const handleSelect = useCallback(
    (id) => {
      // If the same task is actively being polled, don't interrupt it
      const entry = history.find((h) => h.id === id);
      if (!entry) return;

      // If it's a mock entry (from mockData), show the mock result
      const mock = mockResearchEntries.find((m) => m.id === id);
      if (mock) {
        stopPolling();
        setLoading(false);
        setStatusText('');
        setError(null);
        setActiveResult(mock);
        setSelectedId(id);
        return;
      }

      // Real task entry — show existing result or re-trigger polling
      if (entry.status === 'completed' && entry.summary !== undefined) {
        stopPolling();
        setLoading(false);
        setStatusText('');
        setError(null);
        setActiveResult(entry);
        setSelectedId(id);
      }
      // If still running, just update highlight — polling is already in flight
    },
    [history, stopPolling],
  );

  // ── Derived state — what to show in the main workspace ───────────────────
  // Merge mock entries into the history list for the sidebar
  // (shown at the bottom, clearly separated from session history)
  const sidebarHistory = [
    ...history,
    ...mockResearchEntries.map((m) => ({ id: m.id, title: m.title, status: 'completed' })),
  ];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app-layout">
      <Sidebar
        history={sidebarHistory}
        selectedId={selectedId}
        onSelect={handleSelect}
        onNewResearch={handleNewResearch}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />

      <main className={`main-workspace ${sidebarCollapsed ? 'expanded' : ''}`}>
        {loading ? (
          <ResearchResult data={null} loading statusText={statusText} />
        ) : error ? (
          <ResearchResult data={null} loading={false} error={error} onRetry={handleNewResearch} />
        ) : activeResult ? (
          <ResearchResult data={activeResult} loading={false} />
        ) : (
          <ResearchInput onSubmit={handleSubmit} />
        )}
      </main>
    </div>
  );
}
