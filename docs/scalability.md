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
![k6 load test output](<Screenshot 2026-04-05 at 00.12.51.png>)

---

## 2. Silver — Horizontal Scaling with Nginx


---

## 3. Gold — Caching with Redis

