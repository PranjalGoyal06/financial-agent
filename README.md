# SCALE Finance Agent

SCALE Finance Agent is a portfolio-aware investment intelligence prototype. This
development workspace contains a React chat UI, a FastAPI backend, and a
streaming chat runtime that can call Groq when credentials are configured.

The current application includes:

- React frontend in `frontend/`
- FastAPI backend in `backend/`
- Server-sent events chat endpoint at `POST /chat`
- Health endpoint at `GET /health`
- Local user stub with no authentication
- Docker Compose services for Postgres and Chroma

If `GROQ_API_KEY` and `GROQ_MODEL` are not set, the backend uses an explicit
local response so the chat flow can still be tested.

## Prerequisites

- Python 3.11 or 3.12
- uv
- Node.js and npm
- Docker Desktop or another Docker Compose runtime

## Setup

Run all commands from this `dev/` directory.

```bash
uv sync
cd frontend
npm install
cd ..
```

Create a local `.env` file if you want Groq-backed responses:

```bash
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant
```

The app will still run without these values by using the local response path.

## Run Locally

Start the supporting services:

```bash
docker compose up -d
```

Start the backend API:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`.

## Verify

Run backend tests:

```bash
.venv/bin/pytest
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Useful URLs

- Frontend: `http://127.0.0.1:5173/`
- Backend health: `http://127.0.0.1:8000/health`
- Chroma: `http://127.0.0.1:8001/`
