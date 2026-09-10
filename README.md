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

### Optional seeded admin

Set all three of these in `.env` to auto-create a superuser on startup (created
only if missing, and a bad value is logged and skipped rather than crashing):

```env
SEED_ADMIN_USERNAME="admin"
SEED_ADMIN_EMAIL="admin@example.com"   # use a real TLD; .local is rejected
SEED_ADMIN_PASSWORD="Admin123"
```

A superuser can see all host containers (see below).

## Working with a project: analyze → Dockerfile → image → container

Use the **🛠 Projects** tab (or the API directly). The project directory must be
inside the backend's `ALLOWED_PATHS` (default `/home:/workspace:/tmp`).

1. **Add the directory** — type the absolute path (e.g. `/home/eko/my-app`).
2. **Analyze** — detects language, framework, package manager, entrypoint,
   suggested base image, and port (`POST /api/docker/projects/analyze`).
3. **Generate Dockerfile** — preview it, or **Write to disk** to save the
   `Dockerfile` and `.dockerignore` into the project
   (`POST /api/docker/projects/generate-dockerfile`).
4. **Build & Run** — one action that analyzes, writes the Dockerfile, builds the
   image, and starts the container with the port published
   (`POST /api/docker/projects/deploy`). You can override the base image,
   container port, and host port.

The built image is tagged `<dirname>:latest` by default and labeled per user;
the container appears in the **📦 Containers** tab where you can start/stop/remove
it.

Supported project types: Node, Python, Go, Rust, Java (Maven **and** Gradle),
PHP, Ruby, and **static sites** (HTML/JS/CSS with an `index.html`, served via
nginx). Anything else falls back to a generic template. Analysis also reads a
`README` excerpt and lists subdirectories to give richer context.

Java builds use a multi-stage Dockerfile with a build image that already has the
build tool installed (`maven:3.9-eclipse-temurin-21` for Maven,
`gradle:8-jdk21` for Gradle), then run the produced artifact. This avoids relying
on a committed `./mvnw`/`./gradlew` wrapper.

- **Jar projects** (Spring Boot / executable jars) run on `eclipse-temurin:21-jre`
  via `java -jar`.
- **War projects** (`<packaging>war</packaging>`) are detected from the pom and
  deployed into `tomcat:10-jdk21` as `ROOT.war`, since a war needs a servlet
  container rather than `java -jar`.

> Builds can take several minutes (downloading dependencies, compiling). The
> chat and deploy requests use a long client timeout to accommodate this. If a
> build fails, the error usually comes from the **project's own source** (e.g. a
> compilation error), not from dockchat — check the build logs in the deploy
> response.

> Note: **Build & Run / deploy writes a `Dockerfile` and `.dockerignore` into the
> project directory** (they are needed as the build context). Generate + preview
> without writing by using the "Generate Dockerfile" button instead.

### Chat that gathers info by itself

Ask the chat something like *"Create a Dockerfile for /home/eko/data/hextris"*.
When the vLLM server has tool-calling enabled (`VLLM_ENABLE_TOOLS=true`), the
model calls the `analyze_project` tool directly. When tool-calling is **off**
(the default), dockchat detects the path in your message, runs the analyzer
itself, and injects the results into the model's context — so the assistant
answers with real project details instead of asking you for them. The path must
be inside `ALLOWED_PATHS`.

With tool-calling on, the chat can do the full job itself. Available tools:
`analyze_project`, `generate_dockerfile`, `build_image`, `deploy_project`
(analyze → Dockerfile → build → run), `list_containers`, and `create_container`.
Ask it to "build and run" or "deploy" a project and it uses `deploy_project`
rather than telling you to run docker commands manually. `create_container`
requires an image that already exists locally; if it doesn't, the model builds
it first.

**Chat history:** messages are persisted per user in the `chat_messages` table,
so your conversation is restored when you log back in or reload the page. The UI
displays the **full** stored history, while only the most recent 50 messages are
sent to the model as context (to bound token usage). Use the **Clear** button
(or `DELETE /api/chat/history`) to wipe your history. In in-memory mode (no
`DATABASE_URL`) history still works but is lost on backend restart.

Endpoints:
- `GET /api/chat/history` — full history (chronological). Pass `?limit=N` to cap
  to the N most recent messages.
- `DELETE /api/chat/history` — clear the user's history.

**Host port handling:** when a requested host port is already in use, dockchat
automatically picks a free port instead of failing, and reports the mapping
(`ports._remapped_from`). The 📦 Containers tab shows a **Ports (internal →
external)** column, e.g. `80/tcp → 34185` for a published port, or
`5000/tcp (internal only)` for a port that is exposed but not published.

> Building and running requires a working Docker daemon on the backend host
> (`GET /api/docker/status` must report `available: true`).

Example deploy via curl:

```bash
curl -X POST http://localhost:8080/api/docker/projects/deploy \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"path": "/home/eko/my-app", "host_port": 18080}'
```

## Container visibility & isolation

The Containers tab lists only containers **dockchat created**, filtered by a
per-user `dockchat.user=<id>` label. Containers started outside the app (via
`docker run`, docker-compose, etc.) are intentionally hidden for multi-tenant
isolation. If your own list is empty, that's expected until you create a
container through dockchat.

Superusers get an additional **"Admin: all host containers"** view (read-only)
that lists every container on the host, backed by `GET /api/docker/containers/all`
(admin only; normal users receive 403).

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
| `GET/POST /api/docker/containers` | List / create the user's containers |
| `GET /api/docker/containers/all` | List all host containers (admin only) |
| `POST /api/docker/containers/{id}/{action}` | start/stop/restart/remove |
| `GET /api/docker/images` | List images you built |
| `POST /api/docker/images/build` | Build an image from a project directory |
| `POST /api/docker/projects/analyze` | Detect project type |
| `POST /api/docker/projects/generate-dockerfile` | Generate Dockerfile |
| `POST /api/docker/projects/deploy` | Analyze → Dockerfile → build → run, in one call |
| `POST /api/chat` | Chat with tool-calling (persists messages) |
| `GET /api/chat/history` | Full chat history (`?limit=N` to cap) |
| `DELETE /api/chat/history` | Clear the user's chat history |
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

**"Docker daemon is not available" even though `docker ps` works on the CLI**
Caused by the Docker SDK failing with `Not supported URL scheme http+docker`,
an incompatibility between older `docker` SDK versions and modern `urllib3`.
Fixed by pinning `docker>=7.1.0` in `requirements.txt`. Upgrade with
`pip install --upgrade "docker>=7.1.0"` and restart the backend. Note that the
Containers tab only shows containers dockchat created (labeled per user); it
does not list pre-existing containers started outside the app.

## Notes on scope

`sdd.md` describes a 12-week roadmap. This repository implements a working
foundation covering authentication, AI provider management, project analysis,
Dockerfile generation, Docker orchestration, the chat/tool-calling loop, and the
Streamlit UI. Features such as email verification, password reset, rate-limiting
middleware, and docker-compose generation are natural next steps and are noted
in the spec's phased plan.
```
