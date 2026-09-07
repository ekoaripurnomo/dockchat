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

## Quick start (in-memory, no external services)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # leave DATABASE_URL empty for in-memory mode

# Terminal 1 - backend
.venv/bin/uvicorn backend.main:app --reload --port 8080

# Terminal 2 - frontend
.venv/bin/pip install -r frontend/requirements.txt
API_BASE_URL=http://localhost:8080 .venv/bin/streamlit run frontend/app.py
```

Open the Streamlit UI (default http://localhost:8501), register an account, and
start chatting. Interactive API docs are at http://localhost:8080/api/docs.

> In-memory mode does not persist data across restarts. Set `DATABASE_URL` in
> `.env` to enable PostgreSQL persistence.

## Running with PostgreSQL + Redis

```bash
docker compose up -d          # starts postgres (schema auto-loaded) + redis
# set DATABASE_URL in .env, e.g.
#   DATABASE_URL=postgresql://dockchat:dockchat@localhost:5432/dockchat
.venv/bin/uvicorn backend.main:app --reload --port 8080
```

The schema in `backend/db/schema.sql` is applied automatically on startup and by
the Postgres init container.

## Configuration

All settings are read from environment variables / `.env` (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Secret used to sign JWTs (change in production) |
| `DATABASE_URL` | PostgreSQL DSN. Empty = in-memory mode |
| `VLLM_URL` / `VLLM_MODEL` | Local OpenAI-compatible endpoint + model |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Enables the OpenAI provider |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Enables the Anthropic provider |
| `DOCKER_HOST` | Docker daemon socket/URL (defaults to local env) |
| `ALLOWED_PATHS` | Colon-separated dirs the analyzer may read/write |
| `ALLOWED_ORIGINS` | CORS origins for the frontend |

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

## Notes on scope

`sdd.md` describes a 12-week roadmap. This repository implements a working
foundation covering authentication, AI provider management, project analysis,
Dockerfile generation, Docker orchestration, the chat/tool-calling loop, and the
Streamlit UI. Features such as email verification, password reset, rate-limiting
middleware, and docker-compose generation are natural next steps and are noted
in the spec's phased plan.
```
