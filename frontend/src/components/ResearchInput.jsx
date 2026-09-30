import { useState } from 'react';
import './ResearchInput.css';

export default function ResearchInput({ onSubmit, disabled = false }) {
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = query.trim();

    if (!trimmed) {
      setError('Please enter a research topic.');
      return;
    }

    if (trimmed.length < 3) {
      setError('Query must be at least 3 characters.');
      return;
    }

    setError('');
    onSubmit(trimmed);
    setQuery('');
  };

  return (
    <div className="research-input-wrapper">
      <h1 className="research-input-heading">
        What would you like to research?
      </h1>
      <p className="research-input-subtitle">
        Ask a question and get structured research.
      </p>

      <form className="research-input-form" onSubmit={handleSubmit}>
        <textarea
          className="research-textarea"
          placeholder="Enter your research topic..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (error) setError('');
          }}
          aria-label="Research topic"
          disabled={disabled}
        />

        <div className="research-submit-row">
          {error && <span className="validation-msg">{error}</span>}

          <button
            type="submit"
            className="research-submit-btn"
            disabled={disabled}
          >
            Start Research
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </form>
    </div>
  );
}

