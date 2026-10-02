import { useState, useRef, useEffect } from 'react';
import './ResearchInput.css';

/**
 * 4 curated research prompt suggestions matching research, technology, and AI topics.
 */
const EXAMPLE_PROMPTS = [
  'How do vector databases work?',
  'Compare Redis and PostgreSQL for application caching.',
  'Explain the evolution of AI agents.',
  'What are the architectural trade-offs of microservices?',
];

const MAX_QUERY_LENGTH = 500;
const MIN_QUERY_LENGTH = 3;

/**
 * ResearchInput (Research Home) — Focused landing composer where users
 * explore example topics and initiate research tasks.
 *
 * Props:
 *  onSubmit  – (query: string) => void
 *  disabled  – boolean
 */
export default function ResearchInput({ onSubmit, disabled = false }) {
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const textareaRef = useRef(null);

  // Auto-resize textarea to fit content comfortably
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.max(130, textareaRef.current.scrollHeight)}px`;
    }
  }, [query]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    const trimmed = query.trim();

    if (!trimmed) {
      setError('Please enter a research topic or question.');
      return;
    }

    if (trimmed.length < MIN_QUERY_LENGTH) {
      setError(`Query must be at least ${MIN_QUERY_LENGTH} characters.`);
      return;
    }

    if (trimmed.length > MAX_QUERY_LENGTH) {
      setError(`Query must not exceed ${MAX_QUERY_LENGTH} characters.`);
      return;
    }

    setError('');
    onSubmit(trimmed);
  };

  const handleKeyDown = (e) => {
    // Enter without Shift submits; Shift+Enter creates a new line
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && query.trim().length >= MIN_QUERY_LENGTH) {
        handleSubmit();
      }
    }
  };

  const handleSelectExample = (exampleText) => {
    setQuery(exampleText);
    setError('');
    // Focus the textarea so the user can inspect or edit before submitting
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const trimmedLength = query.trim().length;
  const isSubmitDisabled = disabled || trimmedLength < MIN_QUERY_LENGTH || trimmedLength > MAX_QUERY_LENGTH;
  const charCountClass = query.length > MAX_QUERY_LENGTH ? 'char-count error' : 'char-count';

  return (
    <div className="research-home-wrapper">
      <div className="research-home-content">
        {/* ── Welcome Header ─────────────────────────────────── */}
        <header className="research-welcome">
          <div className="research-welcome-badge" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="badge-icon"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            <span>Autonomous AI Research Assistant</span>
          </div>

          <h1 className="research-welcome-heading">
            What would you like to research?
          </h1>
          <p className="research-welcome-subtitle">
            Enter a complex topic or question. ResearchMate searches the web, evaluates verified sources, and synthesizes structured reports with citations.
          </p>
        </header>

        {/* ── Research Composer Card ─────────────────────────── */}
        <section className="research-composer-card" aria-label="Research Topic Composer">
          <form className="research-composer-form" onSubmit={handleSubmit}>
            <div className="composer-textarea-container">
              <textarea
                ref={textareaRef}
                className="composer-textarea"
                placeholder="Ask a research question or explore a topic (e.g. Compare Redis and PostgreSQL for application caching)..."
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  if (error) setError('');
                }}
                onKeyDown={handleKeyDown}
                maxLength={MAX_QUERY_LENGTH + 20}
                aria-label="Research topic or question"
                disabled={disabled}
                rows={4}
              />
            </div>

            {error && (
              <div className="composer-error-banner" role="alert">
                <svg
                  className="error-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{error}</span>
              </div>
            )}

            <div className="composer-footer-row">
              <div className="composer-meta">
                <span className={charCountClass}>
                  {query.length} / {MAX_QUERY_LENGTH}
                </span>
                <span className="composer-shortcut-hint" aria-hidden="true">
                  Press <strong>Enter ↵</strong> to submit · <strong>Shift+Enter</strong> for newline
                </span>
              </div>

              <button
                type="submit"
                className="composer-submit-btn"
                disabled={isSubmitDisabled}
                aria-label="Start autonomous research"
              >
                {disabled ? (
                  <>
                    <span className="submit-spinner" aria-hidden="true" />
                    <span>Submitting…</span>
                  </>
                ) : (
                  <>
                    <span>Start Research</span>
                    <svg
                      className="submit-arrow"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <line x1="5" y1="12" x2="19" y2="12" />
                      <polyline points="12 5 19 12 12 19" />
                    </svg>
                  </>
                )}
              </button>
            </div>
          </form>
        </section>

        {/* ── Example Prompts ─────────────────────────────────── */}
        <section className="research-examples-section" aria-label="Example Research Prompts">
          <p className="examples-section-title">Explore Example Topics</p>
          <div className="examples-grid">
            {EXAMPLE_PROMPTS.map((promptText, idx) => (
              <button
                key={idx}
                type="button"
                className="example-prompt-card"
                onClick={() => handleSelectExample(promptText)}
                disabled={disabled}
                aria-label={`Fill prompt: ${promptText}`}
              >
                <span className="example-prompt-icon" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                </span>
                <span className="example-prompt-text">{promptText}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
