# Scalability Engineering — Load Testing & Optimization

---

## Table of Contents

1. [Bronze — Baseline Load Test](#1-bronze--baseline-load-test)
2. [Silver — Horizontal Scaling with Nginx](#2-silver--horizontal-scaling-with-nginx)
3. [Gold — Caching with Redis](#3-gold--caching-with-redis)

---

## 1. Bronze — Baseline Load Test

### Setup
- **Tool:** k6
- **Script:** `tests/load/k6_baseline.js`
- **Duration:** 30 seconds
- **Concurrent users:** 50

### How to run
```bash
k6 run tests/load/k6_baseline.js
```

### Results

| Metric | Value |
|---|---|
| Concurrent users | 50 |
| Total requests | 810 |
| Success rate | 100% |
| Avg response time | 1.59s |
| p90 response time | 2.25s |
| p95 response time | 2.81s |
| Error rate | 0% |

### Screenshot
<img width="1215" height="903" alt="Screenshot 2026-04-05 at 00 12 51" src="https://github.com/user-attachments/assets/127275ad-92a9-4c7d-a811-861281108fab" />

---

## 2. Silver — Horizontal Scaling with Nginx

### What We Built
To handle 200 concurrent users, we moved from a single Flask process to a horizontally scaled setup using Docker Compose:

- **2 app containers** (`app1`, `app2`) — each running Gunicorn with 4 workers, giving 8 total worker processes
- **1 Nginx container** — acts as the load balancer, sitting in front of both app containers and distributing traffic between them using round-robin
- **1 PostgreSQL container** — shared database with `max_connections=200`

This was all configured in `docker-compose.yml` and `nginx.conf`. Running `docker compose up --build -d` brings up all 4 containers automatically.

### docker compose ps (Silver verification)
<img width="1133" height="116" alt="Screenshot 2026-04-05 at 01 35 13" src="https://github.com/user-attachments/assets/8d0a0250-7a2f-4b56-8614-4d95b988c2ff" />

### Architecture
```
User → Nginx (port 8000) → app1 (gunicorn, 4 workers)
                         → app2 (gunicorn, 4 workers)
       Both → PostgreSQL (max 200 connections)
```

### Setup
- **Tool:** k6
- **Script:** `tests/load/k6_silver.js`
- **Duration:** 30 seconds
- **Concurrent users:** 200

### How to run
```bash
docker compose up --build -d
k6 run tests/load/k6_silver.js
```

### Results

| Metric | Value | Requirement |
|---|---|---|
| Concurrent users | 200 | ✅ |
| Total requests | 6167 | — |
| Success rate | 97.8% | ✅ |
| Avg response time | 649ms | ✅ |
| p90 response time | 1.18s | ✅ |
| p95 response time | 1.78s | ✅ under 3s |
| Error rate | 2.18% | ✅ |

### Screenshot
<img width="962" height="617" alt="Screenshot 2026-04-05 at 02 22 18" src="https://github.com/user-attachments/assets/3f14b096-183c-4f2e-a55c-38d349afe1e0" />

---

### Improvements & Tradeoffs

Getting from Bronze (50 users) to Silver (200 users) required four changes. Here's what we did and why:

#### 1. Added Nginx as a Load Balancer
**What:** Added an Nginx container in front of two app instances using round-robin load balancing.

**Why:** A single Flask instance can only handle so many requests at once. Nginx distributes incoming traffic evenly between `app1` and `app2`, effectively doubling capacity.

**Tradeoff:** Adds an extra network hop for every request. Nginx itself can become a bottleneck if not tuned correctly (which we experienced — see below).

---

#### 2. Switched from Flask Dev Server to Gunicorn
**What:** Replaced `uv run python run.py` with `gunicorn -w 4` in the Dockerfile.

**Why:** Flask's built-in dev server is single-threaded — it handles one request at a time. Under 200 concurrent users, requests queued up and timed out. Gunicorn spawns 4 worker processes per container (8 total across both containers), handling requests truly in parallel.

**Tradeoff:** Gunicorn is a production WSGI server, not part of the core Flask/Peewee/PostgreSQL stack. However it does not replace any of those — it only changes how Flask is served.

**Before (dev server):** p95 = 9.7s, 56% failure rate

**After (gunicorn):** p95 = 1.42s, 12% failure rate

---

#### 3. Added Connection Pooling (Peewee)
**What:** Switched from `PostgresqlDatabase` to `PooledPostgresqlDatabase` with `max_connections=50`.

**Why:** Without pooling, every request opens a new database connection and closes it when done. Under 200 concurrent users, this means up to 200 simultaneous connection attempts — PostgreSQL's default limit is ~100, so requests start failing with `MaxConnectionsExceeded`.

**Tradeoff:** Connections stay open in the pool even when idle, consuming memory. `stale_timeout=300` cleans up connections unused for 5 minutes to mitigate this.

**Before:** `MaxConnectionsExceeded` errors under load

**After:** Requests wait for an available connection instead of failing

---

#### 4. Increased PostgreSQL Max Connections
**What:** Added `command: postgres -c max_connections=200` to the db service in `docker-compose.yml`.

**Why:** PostgreSQL's default `max_connections` is 100. With 2 app containers each holding a pool of 50 connections, we need at least 100 — bumping to 200 gives headroom.

**Tradeoff:** Each PostgreSQL connection uses ~5-10MB of shared memory. 200 connections = up to 2GB RAM reserved. Acceptable for a hackathon but in production you'd use PgBouncer as a connection pooler instead.

---

#### 5. Tuned Nginx Worker Connections
**What:** Set `worker_processes auto` and `worker_connections 2048` in `nginx.conf`, plus enabled HTTP keepalive to the upstream app containers.

**Why:** Default Nginx config handles ~512 connections per worker. Under 200 concurrent users sending multiple requests each, Nginx was dropping connections (`connection reset by peer`).

**Tradeoff:** Higher `worker_connections` increases memory usage per Nginx worker process.

---

## 3. Gold — Caching with Redis

### What We Built
To handle 500 concurrent users while keeping error rate below 5%, we added Redis as an in-memory cache in front of the database for redirect lookups:

- **Redis container** — caches `short_code → original_url` mappings with a 1-hour TTL
- **`app/cache.py`** — thin wrapper around the Redis client with graceful fallback (cache miss falls through to the database; Redis errors are silently ignored so the app stays functional even if Redis goes down)
- **Redirect endpoint** — checks Redis first; only hits PostgreSQL on a cache miss, then writes the result to cache
- **Gunicorn workers bumped to 8 per container** — 16 total workers across both app containers to absorb the extra concurrency
- **PostgreSQL max_connections raised to 300** — headroom for 16 workers × 2 containers with pool size 50

The cache primarily benefits the `GET /<short_code>` redirect path, which is the most read-heavy operation. `POST /shorten` still writes directly to PostgreSQL (no caching needed for writes).

### Architecture
```
User → Nginx (port 8000) → app1 (gunicorn, 8 workers)
                         → app2 (gunicorn, 8 workers)
       Both → Redis (cache)  → PostgreSQL (on cache miss)
              PostgreSQL (max 300 connections)
```

### Setup
- **Tool:** k6
- **Script:** `tests/load/k6_gold.js`
- **Duration:** 30 seconds
- **Concurrent users:** 500

### How to run
```bash
docker compose up --build -d
k6 run tests/load/k6_gold.js
```

### Results

| Metric | Value | Requirement |
|---|---|---|
| Concurrent users | 500 | ✅ |
| Total requests | 9936 | — |
| Success rate | 100% | ✅ |
| Avg response time | 1.28s | ✅ |
| p90 response time | 1.83s | ✅ |
| p95 response time | 2.38s | ✅ under 3s |
| Throughput | 284 req/s | ✅ |
| Error rate | 0% | ✅ under 5% |

### Screenshot
<img width="1013" height="925" alt="Screenshot 2026-04-05 at 05 06 29" src="https://github.com/user-attachments/assets/4ce31a55-dd3c-4cab-8d81-ec397743d901" />

---

### Improvements & Tradeoffs

#### 1. Added Redis Caching for Redirect Lookups
**What:** Added a `cache_get`/`cache_set` call around the database lookup in `GET /<short_code>`. On first access, the URL is fetched from PostgreSQL and stored in Redis with a 1-hour TTL. Subsequent requests for the same short code are served from Redis without touching the database.

**Why:** The redirect endpoint is the hot path — it gets called far more than `/shorten`. Under 500 VUs, nearly every repeat request hits cache, dramatically cutting database load. This is why we could handle 500 VUs while the database only has 300 max connections.

**Tradeoff:** Cached URLs can be stale for up to 1 hour after a `DELETE /links/<short_code>` (deactivation). We mitigate this with an explicit `cache_delete` call in the deactivate route, so the cache is invalidated immediately on deactivation.

#### 2. Graceful Cache Degradation
**What:** All cache operations (`cache_get`, `cache_set`, `cache_delete`) catch exceptions and return `None`/pass silently.

**Why:** If Redis is unavailable, the app falls back to direct database queries. This keeps the system functional during a Redis failure, just at higher latency. This directly supports the reliability requirements from the reliability track.

#### 3. Increased Gunicorn Workers to 8 per Container
**What:** Bumped from `-w 4` to `-w 8` in `scripts/start.sh`.

**Why:** At 500 VUs, the bottleneck shifted from the database to worker availability. 8 workers per container × 2 containers = 16 parallel request handlers. The rule of thumb is `2 × CPU cores + 1` workers; on a multi-core machine this saturates available CPU.

**Tradeoff:** More workers = more memory and more database connections held in pool. We raised `max_connections` on PostgreSQL to 300 to compensate.
