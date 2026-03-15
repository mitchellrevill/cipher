# Quickstart

A compact guide to get the backend and frontend running locally.

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm/yarn/pnpm
- Docker (optional, for container runs)
- pip (bundled with Python) and a virtual environment

## Backend (local)

1. Open a terminal and change into the backend folder:

```bash
cd backend
```

2. Create and activate a virtualenv (examples):

PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
```

4. Copy environment file

Linux/macOS:
```bash
cp .env.example .env
```

PowerShell:
```powershell
Copy-Item .env.example .env
```

Edit `backend/.env` to set any secrets or local overrides.

5. Run the backend in dev mode (auto-reload):

```bash
uvicorn --app-dir src redactor.main:app --reload --host 0.0.0.0 --port 8000
```

The backend listens on port `8000` (the startup script uses this port).

## Backend (Docker)

From the repository root you can build and run the backend container:

```bash
cd backend
docker build -t redactor-backend:dev .
docker run --rm -p 8000:8000 --env-file .env redactor-backend:dev
```

Note: the Docker image exposes port `8000`.

## Frontend (Vite / React)

1. Install and run the frontend dev server:

```bash
cd frontend
pnpm install
pnpm run dev
```

Vite is configured to proxy `/api` to `http://localhost:8000` (see `vite.config.ts`).

Open the UI at `http://localhost:5173` (default Vite port).

## Running both (development)

Open two terminals:

- Terminal A: start the backend (see backend steps).
- Terminal B: start the frontend (`npm run dev`).

Or start both with docker-compose (single command):

```bash
# from repository root
docker-compose up --build
```

This will build and start the `backend` (port 8000) and a containerized `frontend` dev server (port 5173). To stop:

```bash
docker-compose down
```

Alternatively use the provided Makefile:

```bash
make dev   # starts the stack
make down  # stops the stack
```

## Environment variables

- The backend reads `backend/.env` (copy from `backend/.env.example`).
- The frontend reads `frontend/.env` (copy from `frontend/.env.example` if you want a clean local template).
- Do NOT commit real secrets to version control. Use a secret store or Azure App Settings in cloud deployments.

## Authentication setup (MSAL / Microsoft Entra ID)

The app now protects all frontend routes and backend API endpoints with Microsoft Entra ID tokens.

### Frontend auth variables

Set these in `frontend/.env`:

```env
VITE_MSAL_CLIENT_ID=<your-client-id>
VITE_MSAL_AUTHORITY=https://login.microsoftonline.com/<your-tenant-id>
VITE_MSAL_REDIRECT_URI=http://localhost:3000
```

### Backend auth variables

Set these in `backend/.env`:

```env
AZURE_AD_TENANT_ID=<your-tenant-id>
AZURE_AD_CLIENT_ID=<your-client-id>
ENV=development
DEV_BYPASS=true
```

### Required app registration setup

In Microsoft Entra ID / Azure AD, make sure your app registration includes:

- an exposed API scope: `api://<CLIENT_ID>/access_as_user`
- SPA redirect URIs for your local frontend URL and any deployed frontend URL
- delegated permissions such as `openid`, `profile`, and `email`

### Local dev bypass

For local-only development, the app supports a bypass login:

- frontend dev mode accepts any credentials on the login page
- backend accepts `Bearer dev-token-bypass` only when both:
	- `ENV=development`
	- `DEV_BYPASS=true`

If `DEV_BYPASS=true` is set outside development, backend startup will fail intentionally.

## Tests

- Backend tests (pytest):

```bash
cd backend
pytest
```

- Frontend tests (Vitest):

```bash
cd frontend
npx vitest
```

## Helpful commands

- Build frontend for production:

```bash
cd frontend
npm run build
```

- Preview production build locally:

```bash
npm run preview
```

- Lint frontend:

```bash
npm run lint
```

## Where to look next

- Backend source: `backend/src`
- Frontend source: `frontend/src`
- Backend env example: `backend/.env.example`

If you'd like, I can also add a single-script `dev` helper (docker-compose or Makefile) to start both services together.
