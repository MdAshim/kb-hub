# Deployment

**This is a documentation deliverable, not an actual cloud deployment.** Nothing here has
been provisioned on a real VM or cloud account; it describes how you *would* run this
project's Docker Compose stack on a single machine, and what needs to change from the
local-dev defaults to do that safely.

## 1. Why Ollama stays on the host, not in a container

`docker-compose.yml` runs `web` and `huey` in containers but does **not** containerize
Ollama. Two reasons:
- The model itself is a multi-gigabyte download (`llama3.2:3b` is ~2 GB); baking that into
  an image, or managing it as a separate Docker volume, adds real complexity for no benefit
  at this project's scale.
- This setup assumes no GPU passthrough is configured for Docker. Ollama running directly
  on the host can use whatever GPU is available (see the GPU note in this project's own
  troubleshooting from earlier in development); a naive container setup would silently
  fall back to CPU-only inference, which is slower.

A host-installed Ollama (per `docs/LOCAL_SETUP.md`) is exactly what local development
already assumes — Docker just adds `web` and `huey` around it, unchanged.

## 2. Running the stack

```bash
cp .env.example .env          # then edit it -- see the production checklist below
docker compose up -d
```

`docker compose up` migrates the database automatically (the `web` service's command is
`migrate && runserver`) and starts both services against your **already-running** host
Ollama. Check it's actually running first: `ollama list` should show your pulled model.

### Reaching the host's Ollama from inside a container

`.env`'s default `OLLAMA_BASE_URL=http://localhost:11434` will **not** work from inside a
container — `localhost` there resolves to the container itself, not your machine.
`docker-compose.yml` overrides this to `http://host.docker.internal:11434` for both
services.

- **Docker Desktop (macOS / Windows)**: `host.docker.internal` works out of the box.
- **Native Linux (Docker Engine)**: needs the `extra_hosts: ["host.docker.internal:host-gateway"]`
  line already present in `docker-compose.yml` (requires Docker Engine 20.10+). Without it,
  the containers won't be able to reach the host's Ollama at all on Linux.

### On a single VM

The same two commands above are the whole story: install Docker + Docker Compose on the
VM, install Ollama on the VM's host OS (not in a container, per §1) and pull your model,
clone this repo, `cp .env.example .env` and fill in the production values below, then
`docker compose up -d`. Put a reverse proxy (nginx, Caddy) in front of port 8000 for
TLS/domain routing — not set up here, since that's infrastructure outside this project's
scope, not application config.

## 3. Environment variables

All of `.env.example`'s variables apply unchanged in Docker (both services load `.env` via
`env_file:`, so nothing needs duplicating into `docker-compose.yml`). The ones that
specifically need changing for production are in the checklist below; everything else
(chunking, retrieval, `HUEY_WORKERS`, fetch timeouts, etc.) keeps its local-dev meaning.

## 4. Production checklist

These are **not** safe to run with local-dev defaults once this is reachable by anyone
other than you:

- **`DJANGO_DEBUG=False`.** With `DEBUG=True` (the local-dev default), Django serves
  static files itself, shows full tracebacks with source code and local variables on any
  error, and skips host-header validation more permissively. None of that belongs on a
  reachable server.
- **`ALLOWED_HOSTS`** must list your real domain(s) (e.g. `ALLOWED_HOSTS=kb.example.com`).
  The `localhost,127.0.0.1` default will reject every real request once `DEBUG=False`.
- **`DJANGO_SECRET_KEY`** must be a real, unique secret — not `change-me`. Generate one
  with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
- **Static files**: with `DEBUG=False`, Django stops serving static files itself. Run
  `python manage.py collectstatic` (writes to `STATIC_ROOT`, `settings.py`'s
  `BASE_DIR / "staticfiles"`) and serve that directory via your reverse proxy, or add
  WhiteNoise if you'd rather Django serve it directly — neither is wired up here, since
  this project has no custom static assets of its own beyond Django admin's.
- **Do not scale the `huey` service.** `knowledge/vector_store.py`'s write lock is a
  `threading.Lock`, which only serializes writes *within one process*. It provides no
  protection across multiple separate `huey` containers — running more than one
  (`docker compose up --scale huey=2`, or any multi-replica setup) risks two containers
  writing to `data/faiss.index` at once and corrupting it. `HUEY_WORKERS` (thread count
  *within* the single container) is safe to raise; container-level replicas of `huey`
  are not.

## 5. What this deliberately doesn't cover

TLS/certificates, a reverse proxy config, backups of `data/`, monitoring/alerting, secrets
management beyond `.env`, and horizontal scaling of `web` (which would be safe, unlike
`huey`, since it doesn't write to FAISS — but isn't set up here). All out of scope for a
take-home; noted so it's clear these are gaps, not oversights.
