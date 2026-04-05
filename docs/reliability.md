# Reliability Engineering — Test Suite & CI Documentation


---

## Table of Contents

1. [How to Run Tests Locally](#1-how-to-run-tests-locally)
2. [Test Architecture](#2-test-architecture)
3. [Why SQLite Instead of PostgreSQL for Tests](#3-why-sqlite-instead-of-postgresql-for-tests)
4. [Coverage Map](#4-coverage-map)
5. [GitHub Actions CI/CD](#5-github-actions-cicd)
6. [Bug Fixed During Testing](#6-bug-fixed-during-testing)

---

## 1. How to Run Tests Locally

No running database, no `.env` file, no Docker — just:

```bash
# Install all dependencies including dev tools
uv sync --extra dev

# Run all tests with coverage report
uv run pytest --cov=app --cov-report=term-missing -v

# Run with the Silver-tier coverage gate (fails if < 50%)
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=50 -v

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
├── test_api.py         Silver: integration tests for all routes
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

`database.py` calls `PooledPostgresqlDatabase(name, host=..., ...)` inside `init_db()`. We patch `app.database.PooledPostgresqlDatabase` so that call returns a `SqliteDatabase(tmp_path)` instead. The rest of `init_db()` runs unchanged — it still registers the `before_request` / `teardown_appcontext` hooks — but those hooks now manage a SQLite connection.

```python
with patch("app.database.PooledPostgresqlDatabase") as MockPG:
    MockPG.return_value = SqliteDatabase(tmp_path)
    application = create_app()
```

**Why patch at `app.database.PooledPostgresqlDatabase` and not `peewee.PooledPostgresqlDatabase`?**
`unittest.mock.patch` replaces the name **where it is looked up**, not where it is defined. `init_db()` resolves `PooledPostgresqlDatabase` from the `app.database` module's namespace. That is what we patch.

### Trade-off acknowledged

Tests pass on SQLite but the production database is PostgreSQL. The alternative — spinning up a PostgreSQL container in CI — would eliminate the gap but adds complexity and latency. For a hackathon, SQLite is the right trade-off.

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

**Target coverage:** 50% (Silver tier). The `--cov-fail-under=50` flag in CI enforces this gate.

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

- The `test` job runs pytest with `--cov-fail-under=50`. If coverage drops below 50% or any test fails, the job exits non-zero.
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
