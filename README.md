
# NavDrishti — Smart Traffic Management for Ahmedabad

New Vision for Viksit Bharat. AI + real‑time analytics to predict, prevent, and manage congestion.

---
**Video Link** : https://youtu.be/cNr4Wl12kbg


## Table of Contents
- Overview
- Architecture
- Tech Stack
- Quick Start (Windows PowerShell)
- Configuration (env vars)
- Run with VS Code Tasks
- API Quick Check
- Testing
- Troubleshooting
- Project Structure
- Contributors

---

## Overview
NavDrishti is a full‑stack traffic intelligence platform:

- Frontend: ASP.NET Core (Razor + Bootstrap) dashboard with analytics, AI insights, routing and alerts.
- Backend: Python FastAPI with analytics, route analysis, emissions, and mock/real data providers.
- Database: SQLite for development (Alembic migrations ready for production DBs).

Key user features:
- Traffic Dashboard with Overview metrics, AI Predictions, Analytics charts, Alternative Routes, and Alerts in a single scrollable view.
- Project Creation page for route selection and map‑based workflows.
- Analytics endpoints for trends, summaries, emissions, and more.

Related docs: `DOCUMENTATION_INDEX.md`, `PHASE2_INTEGRATION.md`, `PHASE3_IMPLEMENTATION_PLAN.md`, `PHASE4_SUMMARY.md`, `PHASE6_COMPLETE.md`.

---

## Architecture
```
Browser (Razor views + JS)
   └── ASP.NET Core Frontend (Traffic_Frontend)
          └── BackendApiService (HTTP → FastAPI)
                 └── FastAPI Backend (Traffic_Backend)
                        └── SQLAlchemy ORM → SQLite/MySQL
```

- Frontend serves the UI on `http://localhost:5000`
- Backend exposes REST APIs on `http://localhost:8002`

---

## Tech Stack
- Frontend: .NET 8, Razor, Bootstrap 5, Chart.js, Mapbox GL JS
- Backend: FastAPI, Pydantic v2, SQLAlchemy, NetworkX, Uvicorn
- DB: SQLite (dev), Alembic migrations
- Tests: Pytest suite + integration checks

---

## Quick Start (Windows PowerShell)

1) Create and activate a Python virtual env, then install backend deps
```powershell
cd Traffic_Backend
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Set required env vars (Mapbox token needed for maps; SQLite by default)
```powershell
$env:MAPBOX_ACCESS_TOKEN = "<your_mapbox_token>"
$env:SQLALCHEMY_DATABASE_URL = "sqlite:///./navdrishti.db"
```

3) Start the backend (FastAPI on 8002)
```powershell
cd C:\Users\abhis\HSC_NavDrishti_AHM
..\.venv\Scripts\python.exe -m uvicorn Traffic_Backend.main:app --host 0.0.0.0 --port 8002
```

4) Start the frontend (ASP.NET Core on 5000)
```powershell
dotnet run --project "Traffic_Frontend/Traffic_Frontend.csproj" --urls http://localhost:5000
```

5) Open the app
```
http://localhost:5000/Home/Dashboard
```

Notes
- If ports are busy, update `--urls` for frontend and `--port` for backend.
- Razor views may require restarting the frontend to reflect changes.

---

## Configuration (env vars)
- `MAPBOX_ACCESS_TOKEN`: Required for map rendering.
- `SQLALCHEMY_DATABASE_URL`: Defaults to `sqlite:///./navdrishti.db`.
- Optional: auth/JWT settings if you enable auth routes.

Frontend settings
- `Traffic_Frontend/appsettings.json` contains the backend base URL wiring.

---

## Run with VS Code Tasks

Tasks (see `.vscode` or workspace tasks):
- `Run Backend (8002)`: runs `start_backend.ps1` (FastAPI on 8002)
- `Run Frontend`: runs `dotnet` for the ASP.NET Core project on 5000

You can start them from the VS Code command palette → “Run Task…”.

---

## API Quick Check

With the backend running on 8002:
```powershell
Invoke-RestMethod http://localhost:8002/analytics/summary
Invoke-RestMethod "http://localhost:8002/analytics/traffic-trends?hours=24"
```

More endpoints: `Traffic_Backend/API_REFERENCE.md`.

---

## Testing
- Backend unit tests
```powershell
cd Traffic_Backend
pytest -q
```

- Integration smoke test
```powershell
python .\test_phase2_integration.py
```

- Frontend build
```powershell
cd Traffic_Frontend
dotnet build
```

---

## Troubleshooting

Backend fails to start
- Confirm venv active and deps installed: `pip install -r requirements.txt`
- Check port 8002 availability:
```powershell
Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
```

Frontend shuts down immediately
- Run from repo root and point to the project:
```powershell
dotnet run --project "Traffic_Frontend/Traffic_Frontend.csproj" --urls http://localhost:5000
```

No data in Dashboard charts
- Verify analytics endpoints return data (see API Quick Check above)
- Ensure `window.BACKEND_API_URL` resolves to `http://localhost:8002`

Port conflicts
```powershell
Get-NetTCPConnection -LocalPort 5000,8002 -State Listen | Select LocalPort,OwningProcess
```
Stop any blocking process IDs.

---

## Project Structure
```
HSC_NavDrishti_AHM/
├─ Traffic_Frontend/           # ASP.NET Core app
│  ├─ Controllers/
│  ├─ Views/
│  ├─ wwwroot/js/
│  └─ Traffic_Frontend.csproj
├─ Traffic_Backend/            # FastAPI app
│  ├─ routers/
│  ├─ models/
│  ├─ tests/
│  ├─ main.py
│  └─ requirements.txt
├─ start_backend.ps1 / start_frontend.ps1
├─ test_phase2_integration.py
└─ docs/*.md (various phase guides)
```

Useful docs: `DOCUMENTATION_INDEX.md`, `RUN_INSTRUCTIONS.md`, `PHASE4_SUMMARY.md`, `PHASE6_COMPLETE.md`.

---

## Contributors (Team NavDrishti)
- Abhishek H. Mehta
- Krish K. Patel
- Piyush K. Ladumor

---

Last updated: 2025-11-30
