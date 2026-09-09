# dockchat

Chat-controlled Docker container management with AI-powered project scaffolding.

dockchat is a multi-tenant chat application that lets users create, manage, and
deploy Docker containers through natural language. It uses a pluggable AI
provider layer (local vLLM, OpenAI, Anthropic), analyzes projects to generate
production-ready Dockerfiles, and manages the container lifecycle per user.

This implements the design in [`sdd.md`](./sdd.md).

## Architecture

```
frontend/  Streamlit UI (auth, chat, containers, project scaffolding, activity)
backend/   FastAPI app
  config.py            Environment-driven settings
  main.py              App entrypoint + lifespan wiring
  dependencies.py      Singleton service container + auth dependencies
  db/                  Database wrapper (asyncpg pool OR in-memory fallback)
  models/              Pydantic models (user, providers, docker)
  services/            user, audit, ai_provider_manager, docker, project, chat
  routes/              auth, config, docker, chat, audit
```

### Key features

- JWT authentication (access + refresh tokens, bcrypt password hashing)
- Per-user AI provider configuration and runtime switching (vLLM / OpenAI / Anthropic)
- Project analysis (Node, Python, Go, Rust, Java) with Dockerfile + `.dockerignore` generation
- Docker orchestration with per-user container isolation (label namespacing)
- LLM tool-calling: the model can analyze projects, generate Dockerfiles, and manage containers
- Audit logging of user actions
- Runs with **PostgreSQL** for persistence, or in an **in-memory mode** with no
  external dependencies for local development/demos

## Requirements

- Python 3.11+
- Optional: PostgreSQL 16+ and Redis (for persistent multi-tenant use)
- Optional: a running Docker daemon (container features degrade gracefully if absent)

> **Always run commands from the project root** (`dockchat/`), not from inside
> `backend/`. The app is imported as the package path `backend.main:app`, which
> only resolves when the project root is the working directory. Running from
> inside `backend/` fails with `ModuleNotFoundError: No module named 'backend'`.

## Quick start (in-memory, no external services)

```bash
# from the project root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # leave DATABASE_URL empty for in-memory mode

# Terminal 1 - backend (run from project root)
uvicorn backend.main:app --reload --port 8080

# Terminal 2 - frontend (run from project root)
pip install -r frontend/requirements.txt
API_BASE_URL=http://localhost:8080 streamlit run frontend/app.py
```

Open the Streamlit UI (default http://localhost:8501), register an account, and
start chatting. Interactive API docs are at http://localhost:8080/api/docs.

> In-memory mode does not persist data across restarts. Set `DATABASE_URL` in
> `.env` to enable PostgreSQL persistence.

## Authentication: no default account

dockchat ships with an empty user store. **Register once** (UI "Register" tab or
`POST /api/auth/register`), then log in. Password rules: minimum 8 characters
with at least one uppercase letter, one lowercase letter, and one digit.

- In-memory mode: accounts are lost on every backend restart, so re-register.
- PostgreSQL mode: accounts persist.

## Running with PostgreSQL + Redis

```bash
docker compose up -d          # starts postgres (schema auto-loaded) + redis
# set DATABASE_URL in .env, e.g.
#   DATABASE_URL=postgresql://dockchat:dockchat@localhost:5432/dockchat
uvicorn backend.main:app --reload --port 8080   # from project root
```

The schema in `backend/db/schema.sql` is applied automatically on startup and by
the Postgres init container.

### Recreating the schema after a schema change

`CREATE TABLE IF NOT EXISTS` will not alter tables that already exist. If you
change `backend/db/schema.sql` against an existing database (for example the
switch to `TIMESTAMPTZ` columns), drop and recreate the dockchat tables. This
clears all data, so only do it in development:

```bash
source .venv/bin/activate
python - <<'PY'
import asyncio, asyncpg
from pathlib import Path
async def main():
    conn = await asyncpg.connect("postgresql://dockchat:dockchat@localhost:5432/dockchat")
    await conn.execute("""
        DROP TABLE IF EXISTS audit_logs, user_projects, user_containers,
            user_sessions, user_workspaces, user_preferences, users CASCADE;
    """)
    await conn.execute(Path("backend/db/schema.sql").read_text())
    await conn.close()
    print("schema recreated")
asyncio.run(main())
PY
```

## Configuration

All settings are read from environment variables / `.env` (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Secret used to sign JWTs (change in production) |
| `DATABASE_URL` | PostgreSQL DSN. Empty = in-memory mode |
| `VLLM_URL` / `VLLM_MODEL` | OpenAI-compatible endpoint + model |
| `VLLM_API_KEY` | Bearer token for secured vLLM endpoints. **Token only, no `Bearer ` prefix** (the client adds it). Leave empty for local unsecured vLLM |
| `VLLM_ENABLE_TOOLS` | `true` only if vLLM was launched with tool-calling flags (see below). Default `false` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Enables the OpenAI provider |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Enables the Anthropic provider |
| `DOCKER_HOST` | Docker daemon socket/URL (defaults to local env) |
| `ALLOWED_PATHS` | Colon-separated dirs the analyzer may read/write |
| `ALLOWED_ORIGINS` | CORS origins for the frontend |

## AI providers & tool calling

vLLM is the default provider. Basic chat works out of the box. For the model to
**call Docker tools from chat** (analyze projects, generate Dockerfiles, manage
containers), the vLLM server must be launched with tool-calling enabled:

```bash
vllm serve Qwen/Qwen3-8B \
  --enable-auto-tool-choice \
  --tool-call-parser hermes        # parser matching your model family
```

Then set `VLLM_ENABLE_TOOLS=true` in `.env` and restart the backend.

If `VLLM_ENABLE_TOOLS=false` (default), dockchat sends plain chat requests and
also automatically retries without tools if the server rejects them, so chat
always works. The Projects and Containers tabs work directly regardless of this
setting, since they call their own endpoints rather than going through the LLM.

## API overview

| Method & Path | Description |
|---------------|-------------|
| `POST /api/auth/register` \| `login` \| `refresh` \| `logout` | Auth |
| `GET/PUT /api/auth/me` | Current user profile |
| `GET /api/config/providers` | List AI providers |
| `POST /api/config/providers/switch` | Switch active provider |
| `PUT /api/config/providers/{name}/parameters` | Update model params |
| `GET /api/config/providers/{name}/test` | Test connection |
| `GET /api/docker/status` | Docker daemon availability |
| `GET/POST /api/docker/containers` | List / create containers |
| `POST /api/docker/containers/{id}/{action}` | start/stop/restart/remove |
| `POST /api/docker/projects/analyze` | Detect project type |
| `POST /api/docker/projects/generate-dockerfile` | Generate Dockerfile |
| `POST /api/chat` | Chat with tool-calling |
| `GET /api/audit/logs` | User activity log |

## Troubleshooting

**`ModuleNotFoundError: No module named 'backend'`**
You started uvicorn from inside `backend/`. Run it from the project root instead:
`cd dockchat && uvicorn backend.main:app --reload --port 8080`.

**Frontend: `Cannot reach backend: Expecting value: line 1 column 1 (char 0)`**
The frontend got a non-JSON (usually empty) response. Confirm the backend is
running and that `API_BASE_URL` matches its address. Check with
`curl http://localhost:8080/api/health`.

**`can't subtract offset-naive and offset-aware datetimes` (500 on register/login)**
The database was created with the older `TIMESTAMP` schema. Recreate the schema
with `TIMESTAMPTZ` columns (see "Recreating the schema after a schema change").

**`duplicate key value violates unique constraint "user_sessions_token_key"`**
Fixed: tokens now include a unique `jti`. If you see this on an old process,
restart the backend so the updated code is loaded.

**Chat 500: `"auto" tool choice requires --enable-auto-tool-choice ...`**
Your vLLM server was not launched with tool-calling flags. Either set
`VLLM_ENABLE_TOOLS=false` (default; chat still works), or relaunch vLLM with the
flags shown in "AI providers & tool calling" and set `VLLM_ENABLE_TOOLS=true`.

**`401 Unauthorized` from the vLLM endpoint**
Set `VLLM_API_KEY` to the bare token with no `Bearer ` prefix — the client adds
`Bearer` itself, so a prefixed value becomes `Bearer Bearer ...` and fails.

## Notes on scope

`sdd.md` describes a 12-week roadmap. This repository implements a working
foundation covering authentication, AI provider management, project analysis,
Dockerfile generation, Docker orchestration, the chat/tool-calling loop, and the
Streamlit UI. Features such as email verification, password reset, rate-limiting
middleware, and docker-compose generation are natural next steps and are noted
in the spec's phased plan.
```
