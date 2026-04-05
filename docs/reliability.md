# Reliability Engineering — Test Suite & CI Documentation


---

## Table of Contents

1. [How to Run Tests Locally](#1-how-to-run-tests-locally)
2. [Test Architecture](#2-test-architecture)
3. [Why SQLite Instead of PostgreSQL for Tests](#3-why-sqlite-instead-of-postgresql-for-tests)

---

## 1. How to Run Tests Locally

No running database, no `.env` file, no Docker — just:

```bash
# Install all dependencies including dev tools
uv sync --extra dev

# Run all tests
uv run pytest -v

# Run a single file
uv run pytest tests/test_health.py -v

# Run a single test
uv run pytest tests/test_health.py::test_health_returns_200 -v
```

---

## 2. Test Architecture

### File structure

```
tests/
├── conftest.py         Shared fixtures (SQLite swap, test client)
├── test_health.py      Bronze: /health endpoint
└── test_links.py       Bronze: unit tests for generate_short_code()
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
