# MLH PE Hackathon 2026 — URL Shortener

A production-grade URL shortener built for the MLH PE Hackathon 2026. Built on Flask + PostgreSQL, horizontally scaled with Nginx and Redis caching, with full CI/CD and chaos-tested reliability.

**Stack:** Flask · Peewee ORM · PostgreSQL · Redis · Nginx · Gunicorn · Docker · k6 · DigitalOcean

---

## API Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/shorten` | Create a short URL |
| `GET` | `/<short_code>` | Redirect to original URL (Redis cached) |
| `GET` | `/links` | List all active links |
| `DELETE` | `/links/<short_code>` | Deactivate a short link |

### Example

```bash
# Shorten a URL
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
# → {"short_code": "aB3xZ9", "original_url": "https://example.com", ...}

# Redirect
curl -L http://localhost:8000/aB3xZ9
```

---

## Running the App

```bash
# Start all services (Nginx, app1, app2, Redis, PostgreSQL)
docker compose up --build -d

# Verify
curl http://localhost:8000/health
# → {"status": "ok"}
```

---

## Architecture

```
Client
  │
  ▼
Nginx (port 8000)
  ├── app1 (Gunicorn, 8 workers)
  └── app2 (Gunicorn, 8 workers)
        │
        ├── Redis (cache — redirect lookups)
        └── PostgreSQL (primary store)
```

---

## Quest Tracks

### Reliability Engineering

> Goal: Build a system that handles failures gracefully and recovers automatically.

| Level | What We Did |
|-------|-------------|
| Bronze | `/health` endpoint, CI pipeline (GitHub Actions), 53 passing tests |
| Silver | 50%+ test coverage gate in CI, deploy only on green, structured error handling |
| Gold | 70%+ test coverage, `restart: always` chaos resilience, graceful Redis fallback |

CI runs on every PR — tests must pass and coverage must be ≥70% before merge is allowed.

See [`docs/reliability.md`](docs/reliability.md) for full documentation.

---

### Scalability Engineering

> Goal: Handle increasing load without degrading performance.

| Level | Setup | VUs | Success Rate | p95 Latency |
|-------|-------|-----|-------------|-------------|
| Bronze | Single Flask process | 50 | 100% | 2.81s |
| Silver | Nginx + 2 app containers + connection pooling | 200 | 97.8% | 1.78s |
| Gold | + Redis caching + 8 Gunicorn workers per container | 500 | 100% | 2.38s |

Load testing done with [k6](https://k6.io). Scripts in `tests/load/`.

See [`docs/scalability.md`](docs/scalability.md) for full documentation and results.

---

## Project Structure

```
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── cache.py             # Redis cache (get/set/delete with fallback)
│   ├── database.py          # PooledPostgresqlDatabase, connection hooks
│   ├── models/
│   │   ├── link.py          # Link model (short_code, original_url, is_active)
│   │   ├── user.py          # User model
│   │   └── event.py         # Event model (click tracking)
│   └── routes/
│       └── links.py         # All URL shortener routes
├── docs/
│   ├── reliability.md       # Reliability quest documentation
│   └── scalability.md       # Scalability quest documentation + k6 results
├── scripts/
│   ├── init_db.py           # Creates DB tables on startup
│   └── start.sh             # Container entrypoint (migrate + gunicorn)
├── tests/
│   ├── conftest.py          # SQLite swap for tests
│   └── load/
│       ├── k6_baseline.js   # 50 VUs
│       ├── k6_silver.js     # 200 VUs
│       └── k6_gold.js       # 500 VUs
├── docker-compose.yml       # All 5 services
├── nginx.conf               # Load balancer config
└── Dockerfile
```

---

## Troubleshooting

**Containers not starting**
```bash
docker compose logs app1
docker compose logs nginx
```
Check for DB connection errors — the app waits for PostgreSQL to be healthy before starting.

**Nginx "host not found" error**
Nginx started before app containers were ready. Fix:
```bash
docker compose restart nginx
```

**Port 8000 not responding**
```bash
docker compose ps  # check all services are Up
curl http://localhost:8000/health
```

**Out of memory on Droplet**
Add swap space:
```bash
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

**Redis connection errors**
The app degrades gracefully — Redis errors are caught silently and fall back to PostgreSQL. Check Redis is running:
```bash
docker compose ps redis
```

**Database tables missing**
Tables are created automatically on container start via `scripts/init_db.py`. Force recreate:
```bash
docker compose down && docker compose up --build -d
```

---

## Running Tests

```bash
uv sync --dev
uv run pytest --cov=app --cov-report=term-missing
```

---

## Deployment

The app is deployed on a DigitalOcean Droplet (CentOS 9, 1 vCPU, 1GB RAM, Frankfurt region). All 5 services run via Docker Compose on the server — no managed platform, just a raw Linux VM with Docker installed manually.

The Droplet runs 24/7 independently of any local machine. To deploy updates:

```bash
ssh root@206.189.59.175
cd PE-Hackathon-2026
git pull
docker compose up --build -d
```

**Live URL:** `http://206.189.59.175:8000`

---

## Artifacts & Submissions

| Quest | Artifact | Location |
|-------|----------|----------|
| Reliability — All Tiers | Documentation + screenshots | [`docs/reliability.md`](docs/reliability.md) |
| Scalability — All Tiers | Documentation + k6 results + screenshots | [`docs/scalability.md`](docs/scalability.md) |
| Scalability — Load test scripts | k6 scripts (50, 200, 500 VUs) | [`tests/load/`](tests/load/) |
| CI/CD Pipeline | GitHub Actions workflow | [`.github/workflows/`](.github/workflows/) |
| Live Deployment | DigitalOcean Droplet | `http://206.189.59.175:8000` |

---

## AI Usage

We used [Claude Code](https://claude.com/claude-code) (Anthropic's CLI coding assistant, powered by Claude Sonnet) as a pair programming tool.

**How we used it:**
- Debugging Docker and Nginx configuration issues
- Answering questions about connection pooling, Redis caching, and Gunicorn workers
- Helping structure documentation in `docs/scalability.md`

**What we built ourselves:**
- All architectural decisions and quest strategy
- Implemented models, routes, and database setup
- Set up CI/CD pipeline and branch protection rules
- Running k6 load tests, capturing results, and documenting findings
- Redis caching implementation and Docker Compose scaling setup
- DigitalOcean Droplet provisioning and deployment
- All PR reviews and merges

---

## Team

Built by Taofeek and DGbolaga for MLH PE Hackathon 2026.
