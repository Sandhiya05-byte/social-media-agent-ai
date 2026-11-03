# Social Agent Platform

Social Agent Platform is a starter MVP for an AI-assisted social media management system. It combines a React + Vite frontend with a FastAPI + SQLite backend to demonstrate a premium command-center interface and creator profile persistence.

## Phase 1 goals

- Create a premium SaaS-style interface with a persistent sidebar and command center dashboard.
- Set up a FastAPI backend with SQLite persistence.
- Store creator profile data and expose it through REST endpoints.
- Connect the frontend to the API with a clean client layer.
- Validate the API and frontend build with real tests.

## Project structure

- `frontend/` — React + Vite + Tailwind UI
- `backend/` — FastAPI + SQLAlchemy + SQLite API
- `README.md` — setup and usage guide

## Quick start

### 1) Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

The app runs on http://localhost:5174.

### 2) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

The API runs on http://localhost:8001.

## Important files

- `frontend/src/App.jsx` — main dashboard UI
- `frontend/src/components/Sidebar.jsx` — persistent side navigation
- `frontend/src/components/TopNav.jsx` — command bar and creator chip
- `frontend/src/api/client.js` — frontend API client
- `backend/app/main.py` — FastAPI application entry point
- `backend/app/database.py` — SQLite engine and DB bootstrap
- `backend/app/models/creator.py` — creator persistence model
- `backend/app/routers/creator.py` — creator API routes

## Demo data and limitations

This first phase uses clearly labelled demo data where needed and keeps all logic aligned with the required approval gate. It does not claim live publishing to social platforms.

## Testing

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## Acceptance criteria for Phase 1

- User can open the React dashboard and see the premium SaaS layout.
- Creator profile form can save data to the FastAPI backend.
- Data is persisted in SQLite.
- The backend responds at `/api/health`.
- Frontend builds successfully with Vite.

## Phase 2: research agents

Phase 2 adds the first four specialist agents for the research stage:

- Trend Research Agent
- Competitor Intelligence Agent
- Brand Voice Agent
- Hook Generation Agent

Each agent has a clear status, a model interface with a template fallback, and a reusable workflow that combines them.

The research workflow accepts:

- a niche
- public competitor URLs
- creator writing samples
- RSS sources

The response includes ranked topic suggestions, competitor observations, content gap suggestions, scripts, and hook alternatives.

## Phase 4: validation, approval, and scheduling

Phase 4 adds the content review workflow that sits between creative generation and publishing:

- validation rules for required media, scripts, captions, clarity, and platform-specific requirements
- an approval queue with Draft, Validation Failed, Awaiting Approval, Approved, Rejected, Scheduled, Published, and Failed states
- a scheduling backend using APScheduler with SQLite-backed jobs so scheduled work survives restarts
- a publishing calendar UI for scheduling, cancellation, and rescheduling approved content
- explicit human approval gates before any scheduled or published item is released

This MVP keeps publishing local and simulated. It does not claim live Instagram, YouTube, or LinkedIn publishing without verified platform credentials and permissions.

## Future phases

Phase 5 will add stronger orchestration, analytics, workflow persistence, and more complete publisher integrations only when official credentials and permissions are available.
