# Proposal Orchestrator (Minimal Web App)

This project is a multi-agent estimation system into a minimal web application with:

- FastAPI backend (backend/app)
- React frontend (frontend)
- Simple SQLite persistence
- Dropbox SOW import + light parsing for knowledge base
- Admin UI to view/update the rate card

Prerequisites
- Python 3.10+
- Node 16+
- (Optional) Dropbox token for importing historical SOWs (set env var DROPBOX_TOKEN)

Quick start (development)

Backend — get the API running
1. Open a terminal and go to the backend folder:
   ```bash
   cd /workspaces/project-orchestrator/backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate OR .venv\Scripts\Activate.ps1 (for Windows)
   ```
3. Install Python dependencies:
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt or python -m pip install -r requirements-windows.txt
   ```
4. (Optional) Set environment variables (example):
   ```bash
   export DROPBOX_TOKEN="your_dropbox_token"
   ```
5. Start the API:
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 
   ```
6. Verify the API is up:
   ```bash
   $BROWSER http://localhost:8000/docs
   ```

Frontend — run the UI
1. Open another terminal and go to the frontend folder:
   ```bash
   cd /workspaces/project-orchestrator/frontend
   ```
2. (If you had a broken install) clean old artifacts:
   ```bash
   rm -rf node_modules package-lock.json
   ```
3. Install Node deps and start the dev server:
   ```bash
   npm install
   npm start
   ```
4. Open the UI:
   ```bash
   $BROWSER http://localhost:3000
   ```

Run both together — quick options
- Two terminals (recommended): one for backend, one for frontend (follow steps above).
- Single terminal using tmux (example):
  ```bash
  tmux new -s dev -d "bash -lc 'cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000'"
  tmux split-window -h -t dev "bash -lc 'cd frontend && npm start'"
  tmux attach -t dev
  ```

Notes & troubleshooting
- If `uvicorn` is not found, ensure the virtualenv is activated and dependencies installed, or run:
  ```bash
  python -m pip install fastapi uvicorn[standard]
  ```
- If the frontend fails with `react-scripts: not found`, fix package.json (react-scripts 5.0.1) and run `rm -rf node_modules package-lock.json && npm install`.
- If backend import errors mention stray `// filepath:` lines at top of Python files, remove those lines (they are not valid Python).
- Use the admin endpoints to view/update the rate card and to import SOWs from Dropbox.

How it works
- Frontend posts brief project descriptions to /api endpoints.
- Backend returns clarification questions or a completed estimate and a generated SOW.
- Admin endpoints: /api/admin/ratecard and /api/admin/import_sows

Next steps
- Secure admin endpoints for production.
- Improve SOW parsing with an NLP model.
- Add HubSpot integration with proper auth and error handling.
