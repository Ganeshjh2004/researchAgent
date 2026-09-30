# Security

## Authentication Mode
Currently, the API endpoints are **Unauthenticated**. This is designed for local-first execution. If deploying to a network, API key middleware or OAuth must be implemented. Do not expose this service to the public internet without an API gateway.

## Input Validation
All API boundaries are strictly typed using Pydantic. 
- Research queries are clamped to a minimum of 3 and maximum of 500 characters.
- Extraneous fields are ignored.

## File Access Restrictions (Path Traversal)
Report download endpoints (`/api/v1/research/{task_id}/report`) enforce strict basename evaluation. 
```python
safe_filename = Path(filename).name
file_path = REPORTS_DIR / safe_filename
```
This guarantees clients cannot inject `../../` to read arbitrary `.env` files or system binaries. The system explicitly verifies that the constructed path exists inside the dedicated `reports/` folder.

## Secrets Handling
API errors are caught using a generic `try/except` block at the orchestration layer. Raw Python stack traces are intercepted and replaced with generic `500 Internal workflow error occurred.` messages. This ensures that missing or invalid API keys, database URIs, or internal IP configurations are never leaked to the client.

## Remaining Risks
- **Denial of Service (DoS):** There is currently no active rate-limiting (e.g., token buckets). A malicious actor could spam `/api/v1/research` and exhaust the Uvicorn background thread pool, leading to connection starvation.
- **Quota Exhaustion:** Search tools (DuckDuckGo, Wikipedia) and LLM APIs (Groq) will quickly hit rate limits if the endpoint is abused.
