import './ThemeToggle.css';

/**
 * ThemeToggle — accessible button for switching between Light and Dark themes.
 *
 * Props:
 *  theme     – 'light' | 'dark'
 *  onToggle  – () => void
 */
export default function ThemeToggle({ theme = 'light', onToggle }) {
  const isDark = theme === 'dark';
  const label = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  return (
    <button
      type="button"
      className="theme-toggle-btn"
      onClick={onToggle}
      aria-label={label}
      title={label}
    >
      <span className="theme-toggle-icon-wrap" aria-hidden="true">
        {isDark ? (
          /* Sun Icon */
          <svg
            className="theme-toggle-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2" />
            <path d="M12 20v2" />
            <path d="m4.93 4.93 1.41 1.41" />
            <path d="m17.66 17.66 1.41 1.41" />
            <path d="M2 12h2" />
            <path d="M20 12h2" />
            <path d="m6.34 17.66-1.41 1.41" />
            <path d="m19.07 4.93-1.41 1.41" />
          </svg>
        ) : (
          /* Moon Icon */
          <svg
            className="theme-toggle-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
          </svg>
        )}
      </span>
      <span className="theme-toggle-label">
        {isDark ? 'Light mode' : 'Dark mode'}
      </span>
    </button>
  );
}
