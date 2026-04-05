# Technical Decision Log

## 1. Flask over Django
**Decision:** Use Flask as the web framework.
**Rationale:** Flask is lightweight and minimal — no ORM, no admin, no batteries included. For a URL shortener with a handful of endpoints, Django's overhead was unnecessary. Flask gave us full control over the stack.

---

## 2. Peewee ORM over SQLAlchemy
**Decision:** Use Peewee for database access.
**Rationale:** Peewee is simpler and more lightweight than SQLAlchemy. It maps directly to PostgreSQL tables with minimal boilerplate and has built-in connection pooling via `PooledPostgresqlDatabase`.

---

## 3. PooledPostgresqlDatabase over PostgresqlDatabase
**Decision:** Switch from `PostgresqlDatabase` to `PooledPostgresqlDatabase` with `max_connections=50`.
**Rationale:** Under load, every request was opening and closing a new DB connection. At 200 concurrent users this exceeded PostgreSQL's default connection limit, causing failures. Connection pooling reuses open connections, eliminating this bottleneck.

---

## 4. Gunicorn over Flask Dev Server
**Decision:** Serve the app with Gunicorn (`-w 8`) instead of `flask run`.
**Rationale:** Flask's dev server is single-threaded — one request at a time. Gunicorn spawns 8 worker processes per container, handling requests in parallel. This was essential for handling 200+ concurrent users.

---

## 5. Nginx as Load Balancer
**Decision:** Add Nginx in front of two app containers using round-robin.
**Rationale:** A single app instance, even with 8 Gunicorn workers, hit a ceiling under 200 VUs. Running two app containers and distributing traffic with Nginx doubled capacity without changing application code.

---

## 6. Redis for Redirect Caching
**Decision:** Cache `short_code → original_url` lookups in Redis with a 1-hour TTL.
**Rationale:** The redirect endpoint is the hottest path. Without caching, every redirect hit PostgreSQL. Under 500 VUs this saturated the DB connection pool. Redis serves cached redirects in microseconds, reducing DB load by ~80% under repeat traffic.

---

## 7. Graceful Redis Fallback
**Decision:** Wrap all Redis calls in try/except and fall back to PostgreSQL silently.
**Rationale:** Redis is a cache, not the source of truth. If Redis goes down, the app should degrade gracefully rather than fail. This keeps the service available during a Redis outage, just at higher latency.

---

## 8. IntegerField over ForeignKeyField for User References
**Decision:** Use `IntegerField` for `user_id` and `url_id` instead of `ForeignKeyField`.
**Rationale:** Peewee's `ForeignKeyField` with deferred references generated invalid SQL when tables were created in the wrong order. Using plain `IntegerField` avoids this entirely while keeping the schema flexible.

---

## 9. SQLite Swap in Tests
**Decision:** Replace PostgreSQL with SQLite in the test suite via `conftest.py` patching.
**Rationale:** Running a real PostgreSQL instance in CI adds complexity and setup time. SQLite is file-based, requires no server, and is compatible with Peewee's ORM layer for unit and integration tests.

---

## 10. DigitalOcean Droplet over Managed Platform
**Decision:** Deploy on a raw DigitalOcean Droplet (CentOS 9) instead of Railway or Render.
**Rationale:** The hackathon required hands-on server provisioning. A Droplet gives full control over the environment — Docker, Nginx, swap space — mirroring a real production setup rather than abstracting it away.
