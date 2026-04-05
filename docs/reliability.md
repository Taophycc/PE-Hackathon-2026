# Reliability Engineering — Test Suite & CI Documentation

---

## Quest Summary

| Tier | Requirement | Evidence | Screenshot |
|------|-------------|----------|------------|
| Bronze | `/health` endpoint working | [Section 9](#9-failure-modes) | <!-- Add /health curl screenshot --> |
| Bronze | Unit tests + pytest collection | [Section 1](#1-how-to-run-tests-locally) | <!-- Add pytest output screenshot --> |
| Bronze | CI workflow configured | [Section 5](#5-github-actions-cicd) | <!-- Add GitHub Actions screenshot --> |
| Silver | 50%+ test coverage | [Section 4](#4-coverage-map) | <!-- Add coverage report screenshot --> |
| Silver | Integration/API tests | [Section 2](#2-test-architecture) | <!-- Add test run screenshot --> |
| Silver | Error handling documented | [Section 9](#9-failure-modes) | <!-- Add error response screenshot --> |
| Gold | 70%+ coverage gate in CI | [Section 5](#5-github-actions-cicd) | <!-- Add CI pass screenshot --> |
| Gold | Structured error responses | [Section 9](#9-failure-modes) | <!-- Add structured error screenshot --> |
| Gold | Service restart after failure | [Section 10](#10-chaos-mode--docker-restart-policy) | <!-- Add chaos demo screenshot --> |
| Gold | Failure modes documented | [Section 9](#9-failure-modes) | — |

---

## Table of Contents

1. [How to Run Tests Locally](#1-how-to-run-tests-locally)
2. [Test Architecture](#2-test-architecture)
3. [Why SQLite Instead of PostgreSQL for Tests](#3-why-sqlite-instead-of-postgresql-for-tests)
4. [Coverage Map](#4-coverage-map)
5. [GitHub Actions CI/CD](#5-github-actions-cicd)
6. [Bug Fixed During Testing](#6-bug-fixed-during-testing)
7. [Known Behavioural Quirks](#7-known-behavioural-quirks)
8. [SQLite vs PostgreSQL Divergence](#8-sqlite-vs-postgresql-divergence)
9. [Failure Modes](#9-failure-modes)
10. [Chaos Mode — Docker Restart Policy](#10-chaos-mode--docker-restart-policy)

---

## 1. How to Run Tests Locally

No running database, no `.env` file, no Docker — just:

```bash
# Install all dependencies including dev tools
uv sync --extra dev

# Run all tests with coverage report
uv run pytest --cov=app --cov-report=term-missing -v

# Run with the Gold-tier coverage gate (fails if < 70%)
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=70 -v

# Run a single file
uv run pytest tests/test_api.py -v

# Run a single test
uv run pytest tests/test_api.py::TestShorten::test_valid_https_url_returns_201 -v
```

---

## 2. Test Architecture

### File structure

```
tests/
├── conftest.py         Shared fixtures (SQLite swap, test client)
├── test_health.py      Bronze: /health endpoint
├── test_errors.py      Silver: JSON error handlers (404, 405, 500)
├── test_links.py       Bronze: unit tests for generate_short_code()
├── test_api.py         Silver/Gold: integration tests for all routes
└── test_models.py      Silver: model CRUD + constraint tests
```

### Fixture hierarchy

```
app (function-scoped)
 └── creates a fresh temp-file SQLite DB per test
 └── creates tables before the test
 └── drops tables after the test
 └── deletes the temp file

client (function-scoped)
 └── wraps app in Flask's test client
```

**Why function-scoped?** Every test gets a completely empty database. This guarantees test independence — a row inserted by test A cannot interfere with test B. The cost is a small amount of setup/teardown overhead per test, which is acceptable.

---

## 3. Why SQLite Instead of PostgreSQL for Tests

### The goal

Tests must run in CI without spinning up a real PostgreSQL server. We want fast, hermetic, zero-dependency tests.

### Why `:memory:` doesn't work here

SQLite's `:memory:` mode creates a new empty database for every new **connection**. Flask closes and reopens the database connection after every request (via `teardown_appcontext` / `before_request`). This means:

- Test setup creates tables on connection #1.
- `POST /shorten` opens connection #2 → empty DB → no tables → crash.

The data does not survive the first request. `:memory:` only works if you use a single persistent connection, which conflicts with Flask's per-request lifecycle.

### The solution: temp-file SQLite

A named temp file (`/tmp/xxxxx.db`) persists across open/close cycles. Each connection opens the same file and sees the same tables and rows. After the test, the file is deleted.

### The patching strategy

`database.py` calls `PostgresqlDatabase(name, host=..., ...)` inside `init_db()`. We patch `app.database.PostgresqlDatabase` so that call returns a `SqliteDatabase(tmp_path)` instead. The rest of `init_db()` runs unchanged — it still registers the `before_request` / `teardown_appcontext` hooks — but those hooks now manage a SQLite connection.

```python
with patch("app.database.PostgresqlDatabase") as MockPG:
    MockPG.return_value = SqliteDatabase(tmp_path)
    application = create_app()
```

**Why patch at `app.database.PostgresqlDatabase` and not `peewee.PostgresqlDatabase`?**
`unittest.mock.patch` replaces the name **where it is looked up**, not where it is defined. `init_db()` resolves `PostgresqlDatabase` from the `app.database` module's namespace. That is what we patch.

### Trade-off acknowledged

Tests pass on SQLite but the production database is PostgreSQL. We acknowledge this. See [Section 8](#8-sqlite-vs-postgresql-divergence) for specifics. The alternative — spinning up a PostgreSQL container in CI — would eliminate the gap but adds complexity and latency. For a hackathon, SQLite is the right trade-off.

---

## 4. Coverage Map

| File | Lines tested | What covers it |
|------|-------------|----------------|
| `app/__init__.py` | create_app(), health() | test_health.py |
| `app/database.py` | init_db(), before_request, teardown | all tests (via requests) |
| `app/errors.py` | 404, 405, 500 handlers | test_errors.py |
| `app/models/__init__.py` | imports | test_models.py |
| `app/models/link.py` | generate_short_code(), Link model | test_links.py, test_models.py |
| `app/models/user.py` | User model | test_models.py |
| `app/models/event.py` | Event model | test_models.py |
| `app/routes/__init__.py` | register_routes() | all tests |
| `app/routes/links.py` | all 4 routes, all branches | test_api.py |

**Target coverage:** 70% (Gold tier). The `--cov-fail-under=70` flag in CI enforces this gate.

### Branches intentionally not covered

- **500 from DB unreachable at startup:** Covered via mock (`side_effect=RuntimeError`) in `test_errors.py::test_500_internal_error_returns_json`. Not tested against a genuinely killed database because that requires infrastructure-level chaos (see Section 10).
- **Short code generation exhaustion (for/else):** Covered in `test_api.py::TestShorten::test_duplicate_custom_code_returns_409` via the duplicate-code path. The 10-retry `for/else` branch that returns 500 is covered by mocking `generate_short_code` to always return a taken code.

---

## 5. GitHub Actions CI/CD

**File:** `.github/workflows/ci.yml`

### Workflow design

```
push to any branch  ──►  test job
pull_request to main ─►  test job
                              │
                         (pass/fail)
                              │
                         deploy-gate job (needs: test)
```

- The `test` job runs pytest with `--cov-fail-under=70`. If coverage drops below 70% or any test fails, the job exits non-zero.
- The `deploy-gate` job uses `needs: test`. GitHub Actions will not start a job whose dependencies failed. This is the **gatekeeper** — broken tests block the deploy step from ever running.

### Why no PostgreSQL service in CI?

The test suite uses SQLite (see Section 3). This means:
- No `services:` block needed.
- No wait time for database readiness.
- CI runs faster and with fewer moving parts.

### Caching

`astral-sh/setup-uv@v5` with `enable-cache: true` caches the uv virtual environment. Subsequent pushes that don't change `pyproject.toml` skip re-downloading packages — typically saves 20–40 seconds per run.

---

## 6. Bug Fixed During Testing

### Missing `updated_at` in `Link.create()`

**File:** `app/routes/links.py` — `POST /shorten` route
**Discovery:** Writing integration tests revealed that `Link.create()` was called without the `updated_at` field. The model defines `updated_at = DateTimeField()` with no `null=True`, meaning NOT NULL is enforced. This would raise an `IntegrityError` on any strict backend.

**Before (broken):**
```python
link = Link.create(
    short_code=short_code,
    original_url=original_url,
    is_active=True,
    created_at=datetime.now(timezone.utc),
)
```

**After (fixed):**
```python
now = datetime.now(timezone.utc)
link = Link.create(
    short_code=short_code,
    original_url=original_url,
    is_active=True,
    created_at=now,
    updated_at=now,
)
```

The same fix was applied to `deactivate_link`, which was calling `link.save()` without updating `updated_at` to the current time — semantically wrong (the record changed but the timestamp didn't update).

**Why tests catch what manual testing misses:** SQLite in development mode may or may not enforce NOT NULL depending on how the database was created. PostgreSQL always enforces it. The test suite caught this before it could fail in production.

---

## 7. Known Behavioural Quirks

### Double-deactivate returns 200 (not 404)

`DELETE /links/<code>` fetches the link with `Link.get(Link.short_code == code)`. This query finds the link regardless of its `is_active` status. If you deactivate the same link twice:
- First call: finds active link → sets `is_active=False` → 200
- Second call: finds inactive link → sets `is_active=False` again → 200

This is **idempotent** (applying it twice gives the same result) but arguably misleading — the second response implies a change happened. The behaviour is tested and documented in `test_api.py::TestDeactivate::test_double_deactivate_is_idempotent`.

**Implication:** If you want a strict "already deactivated" error, add a check: `if not link.is_active: return jsonify(error="Already deactivated"), 409`.

---

## 8. SQLite vs PostgreSQL Divergence

Tests use SQLite; production uses PostgreSQL. Differences to be aware of:

| Behaviour | SQLite | PostgreSQL |
|-----------|--------|------------|
| `CharField(max_length=20)` | Advisory only — longer strings accepted | Enforced — raises error |
| `DateTimeField` storage | Text (ISO 8601 string) | Native `TIMESTAMP` type |
| `RETURNING id` after INSERT | `lastrowid` used instead | Native `RETURNING` clause |
| Concurrent writes | Locks the whole file | Row-level locking |
| Case-sensitive `LIKE` | Default case-insensitive | Case-sensitive |

**What this means for you:** A test can pass on SQLite but fail on PostgreSQL if it exercises any of the above divergences. The most likely candidate is `max_length` on `short_code`: a client sending a 21-character custom code will pass SQLite tests but fail on PostgreSQL.

---

## 9. Failure Modes

| Trigger | Observed behaviour | HTTP response |
|---------|--------------------|---------------|
| Database unreachable at startup | `db.connect()` raises in `before_request`, Flask propagates as unhandled exception | 500 `{"error": "Internal server error"}` |
| Database dies mid-request | Same as above | 500 |
| Malformed / non-JSON body on POST /shorten | `get_json(silent=True)` returns `None`, caught by `if not data` check | 400 |
| Missing `url` key | Caught by `"url" not in data` | 400 |
| Empty or whitespace URL | Caught by `.strip()` + `if not original_url` | 400 |
| URL without http/https scheme | Caught by `startswith(("http://", "https://"))` | 400 |
| Custom `short_code` already taken | Caught by `.exists()` query | 409 |
| All 10 generated short codes already exist | `for/else` exhaustion path | 500 `{"error": "Could not generate unique short code"}` |
| `GET /<code>` for non-existent code | `DoesNotExist` caught | 404 |
| `GET /<code>` for inactive link | `is_active` check | 410 |
| Route not found | Flask 404 handler | 404 `{"error": "Not found"}` |
| Wrong HTTP method | Flask 405 handler | 405 `{"error": "Method not allowed"}` |
| Unhandled exception anywhere | Flask 500 handler | 500 `{"error": "Internal server error"}` |

<img width="471" height="51" alt="Screenshot 2026-04-04 at 21 33 12" src="https://github.com/user-attachments/assets/4c29f1b4-6f05-4b37-87e8-40a870f708ae" />


### Gap: no retry on DB failure

The current code has no reconnect logic. If the database becomes temporarily unavailable (brief restart, network blip), every request fails with a 500 until the DB comes back. For production resilience, consider:
- Connection pooling with `playhouse.pool.PooledPostgresqlDatabase`
- A retry decorator on `before_request`

---

## 10. Chaos Mode — Docker Restart Policy

**Relevant to:** Gold Tier — "Kill the container → Watch it resurrect."

The `docker-compose.yml` already has `restart: always` on both `app` and `db` services:

```yaml
services:
  app:
    restart: always   # Docker restarts the container if it crashes or is killed
  db:
    restart: always
```

### How to demo chaos mode

```bash
# Start services
docker compose up -d

# Find the running app container
docker ps

# Kill it hard (simulates a crash at 2 AM)
docker kill <container_id>

# Watch Docker bring it back automatically (usually within 1-2 seconds)
docker ps

# Verify the app recovered
curl http://localhost:5000/health
# → {"status": "ok"}
```
<img width="1136" height="659" alt="Screenshot 2026-04-04 at 21 29 15" src="https://github.com/user-attachments/assets/c60c2b96-5cb7-4e81-873e-99b56aed2dfc" />

`restart: always` means Docker restarts the container immediately on any exit, regardless of exit code. This covers:
- Application crashes (unhandled exceptions that exit the process)
- OOM kills
- Manual `docker kill`
- Host machine reboots (`restart: unless-stopped` would skip that last case)

The `db` service has a healthcheck (`pg_isready`) and the `app` service has `depends_on: db: condition: service_healthy`, so the app won't start until PostgreSQL is actually ready to accept connections — preventing the race condition where the app starts before the DB is up.
