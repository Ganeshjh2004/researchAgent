# AI Research Agent

The AI Research Agent is a functional AI Research Agent MVP and demonstration-ready asynchronous research system. It accepts user research queries, executes an orchestrated workflow using external search engines (DuckDuckGo, Wikipedia), synthesizes the gathered information using a Large Language Model (Groq), and generates downloadable Markdown reports. The system is decoupled into a FastAPI backend (with a Redis-backed async worker) and a modern React/Vite frontend.

---

## Features

- **Asynchronous Research Task Submission:** Submit complex queries without blocking the UI.
- **Task Status Tracking:** Polling mechanism to track real-time task progression (`queued` → `running` → `completed`).
- **LangGraph Research Workflow:** A directed state graph ensuring reliable validation, research, synthesis, and output generation.
- **Web Search Tools:** Integrates DuckDuckGo and Wikipedia for live data gathering.
- **Groq-powered Synthesis:** Fast, high-quality information summarization and report generation.
- **Redis Task Queue & Worker:** Decoupled background processing ensuring application resilience.
- **React Frontend:** A responsive, ChatGPT-style interface for interacting with the agent.
- **Research Result Rendering:** Renders a ~300-line Markdown summary preview with structured, clickable source references.
- **Report Download:** Full research reports are saved to disk and can be downloaded as `.txt` files.

---

## Screenshots
*(Future placeholder for UI screenshots)*

---

## Technology Stack

**Frontend:**
- React (v19)
- Vite
- JavaScript
- CSS (Vanilla)
- React Markdown

**Backend:**
- Python 3.12+
- FastAPI & Uvicorn
- Pydantic

**AI & Orchestration:**
- LangGraph
- LangChain
- Groq LLM

**Infrastructure:**
- Redis (Task Queuing and State Management)

**Research Providers:**
- DuckDuckGo (Structured search with URLs)
- Wikipedia (Encyclopedic search)

---

## Architecture

The system uses a highly decoupled architecture:
- **Frontend (React)** communicates with the **FastAPI Backend** via REST.
- **FastAPI** validates the request, generates a UUID, persists the initial state to **Redis**, and pushes the task to a processing queue.
- An independent **Python Worker** pulls from the queue, invoking the **LangGraph** orchestrator.
- The workflow coordinates the **Search Tools** and **Groq LLM** to produce a report, saving the full text to the local disk and updating the Redis task state.
- The **Frontend** polls for completion and ultimately displays the summary preview and a download link.

For a deep dive and visual diagrams, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Research Workflow

1. User submits research query via the React UI.
2. FastAPI validates the request and generates a Task ID.
3. Task is persisted as a Hash in Redis and its ID is pushed to a List (`research:queue`).
4. The background Worker claims the task atomically.
5. The LangGraph `StateGraph` executes:
   - Validates input length.
   - Triggers DuckDuckGo and Wikipedia tools concurrently.
   - Validates the retrieved research volume.
   - Groq synthesizes the findings into a comprehensive report.
   - Validates the final LLM output.
   - Saves the report to the local filesystem.
6. The Worker updates the Redis task state to `completed` with summary metadata and source URLs.
7. The Frontend retrieves the completed result and renders the Markdown preview.
8. The User can click inline links to download the full `.txt` report.

---

## Project Structure

```
AI Agent/
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── api.py                    # FastAPI entry point
├── worker.py                 # Background task worker
├── research_workflow.py      # LangGraph state machine definition
├── tools.py                  # Search tool configurations
├── long_term_tools.py        # Additional/experimental tool definitions
│
├── docs/                     # Detailed architectural & operational docs
│   └── ARCHITECTURE.md       
│
├── reports/                  # Generated full research reports (.txt)
│
├── e2e_test_api.py           # E2E tests
├── test_api.py               # API tests
├── test_research_workflow.py # Workflow tests
├── test_router.py            # Router tests
├── test_worker_recovery.py   # Worker recovery tests
│
└── frontend/                 # React/Vite web application
    ├── package.json
    ├── package-lock.json
    ├── .env.example          # Frontend environment variables template
    ├── index.html
    ├── vite.config.js
    └── src/
        ├── App.jsx           # Main React component
        ├── components/       # UI components (Sidebar, ResearchInput, etc.)
        ├── services/         # API integration (researchApi.js)
        ├── data/             # Mock data
        ├── App.css           # Layout styling
        └── index.css         # Global variables & reset
```

---

## Prerequisites

- **Python:** 3.12 or newer
- **Node.js:** 20.19.0+ or 22.12.0+ (required by Vite 8)
- **Redis:** Local Redis server running on port `6379`
- **Groq API Key:** Required for the LLM synthesis

---

## Installation and Setup

### 1. Redis
Ensure Redis is installed and running on your machine. On Windows, you can use WSL, Memurai, or a native port.
```powershell
redis-server
```

### 2. Backend Setup
Navigate to the project root and create a virtual environment:
```powershell
cd "D:\AI Agent"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory by copying the example:
```powershell
Copy-Item .env.example .env
```
Open `.env` and insert your actual `GROQ_API_KEY`. (Never commit this file).

For the frontend, copy its environment template:
```powershell
cd frontend
Copy-Item .env.example .env
```
*(The default `VITE_API_BASE_URL` in `frontend/.env` is `http://localhost:8000`, which works out of the box).*

### 4. Frontend Setup
Install NPM dependencies:
```powershell
cd frontend
npm install
```

---

## Running the Application

For the application to function end-to-end, you must run the API, the Worker, and the Frontend simultaneously in separate terminal windows.

**Terminal 1 (Redis):**
```powershell
redis-server
```

**Terminal 2 (FastAPI Backend):**
```powershell
# From project root
.\venv\Scripts\Activate.ps1
.\venv\Scripts\uvicorn.exe api:app --host 127.0.0.1 --port 8000
```

**Terminal 3 (Background Worker):**
```powershell
# From project root
.\venv\Scripts\Activate.ps1
.\venv\Scripts\python.exe worker.py
```

**Terminal 4 (React Frontend):**
```powershell
cd frontend
npm run dev
```
The application will be accessible at `http://localhost:5173`.

---

## API Reference

### Health Check
**GET** `/health`
Returns the status of the API and its Redis connection.

### Submit Research Task
**POST** `/api/v1/research`
**Body:** `{"query": "string"}`
**Response:** `{"task_id": "uuid", "status": "queued", "query": "string", "error": null}`

### Check Task Status
**GET** `/api/v1/research/{task_id}`
**Response:**
```json
{
  "task_id": "uuid",
  "status": "running",
  "query": "string",
  "error": null
}
```

### Retrieve Task Result Metadata
**GET** `/api/v1/research/{task_id}/result`
**Response:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "query": "string",
  "filename": "research_topic_timestamp.txt",
  "summary": "Markdown text preview (~300 lines max)",
  "sources": [
    { "name": "Source Title", "url": "https://example.com" }
  ],
  "error": null
}
```

### Download Full Report
**GET** `/api/v1/research/{task_id}/report`
Returns the raw `.txt` file for download.

---

## Testing

Unit and E2E tests are available in the root directory. To run tests, activate the virtual environment and execute them via Python. 
*(Note: To test worker recovery securely, ensure the main `worker.py` daemon is stopped).*
```powershell
.\venv\Scripts\python.exe test_api.py
.\venv\Scripts\python.exe test_worker_recovery.py
.\venv\Scripts\python.exe test_research_workflow.py
```
To run the End-to-End test, ensure `api:app` and `worker.py` are both actively running:
```powershell
.\venv\Scripts\python.exe e2e_test_api.py
```

---

## Limitations

- **Redis Dependency:** Redis serves as the sole state management backend. If it crashes without persistence enabled, all queued tasks are lost.
- **Rate Limits:** External search providers (DuckDuckGo, Wikipedia) have strict, undocumented rate limits that may occasionally cause workflow validations to fail.
- **Volatile Session History:** Task history is only saved in the React application's local state and will clear upon a browser refresh.
- **Wikipedia URLs:** The LangChain Wikipedia tool returns plain text without source URLs, so Wikipedia citations in the UI are not clickable.
- **Preview Truncation:** The UI displays a maximum of approximately 300 lines of the report to prevent rendering overload; the rest must be downloaded.

---

## Future Improvements

- **Persistent Session History:** Implement database storage (e.g., PostgreSQL/MongoDB) to save user sessions across browser reloads.
- **Authentication:** Add user login, API keys, and rate-limiting.
- **WebSocket Integration:** Replace polling with real-time WebSocket updates for task progression.
- **Multi-Agent Expansion:** Add specialized agents for deep-dive technical research vs general summaries.

---

## License

No license has been selected for this project.
