# Operations Runbook — URL Shortener

## Service Overview

| Service | Role | Port |
|---------|------|------|
| nginx | Load balancer / reverse proxy | 8000 (public) |
| app1 | Flask app (Gunicorn, 8 workers) | 8000 (internal) |
| app2 | Flask app (Gunicorn, 8 workers) | 8000 (internal) |
| redis | URL cache | 6379 (internal) |
| db | PostgreSQL database | 5432 (internal) |

**Live URL:** `http://206.189.59.175:8000`

---

## Health Check

```bash
curl http://206.189.59.175:8000/health
# Expected: {"status": "ok"}
```

Check all containers are running:
```bash
ssh root@206.189.59.175
cd PE-Hackathon-2026
docker compose ps
```

All services should show `Up`.

---

## Deployment

### First-time deploy
```bash
ssh root@206.189.59.175
git clone https://github.com/Taophycc/PE-Hackathon-2026.git
cd PE-Hackathon-2026
docker compose up --build -d
```

### Deploy updates
```bash
ssh root@206.189.59.175
cd PE-Hackathon-2026
git pull
docker compose up --build -d
```

### Rollback
```bash
git log --oneline -5          # find the commit to roll back to
git checkout <commit-hash>
docker compose up --build -d
```

---

## Restart Services

```bash
# Restart everything
docker compose restart

# Restart a specific service
docker compose restart nginx
docker compose restart app1
docker compose restart redis
```

---

## View Logs

```bash
# All services
docker compose logs --tail=50

# Specific service
docker compose logs app1 --tail=50
docker compose logs nginx --tail=50
```

---

## Common Incidents

### App not responding on port 8000
1. Check nginx: `docker compose ps nginx`
2. If restarting: `docker compose restart nginx`
3. Check app containers: `docker compose logs app1 --tail=20`

### High error rate under load
1. Check DB connections: `docker compose logs app1 | grep connection`
2. Check Redis: `docker compose ps redis`
3. Restart app containers: `docker compose restart app1 app2`

### Container crashed
All services have `restart: always` — they restart automatically. To verify:
```bash
docker compose ps   # check STATUS column
docker compose logs <service> --tail=20   # check why it crashed
```

### Out of memory
```bash
free -h   # check available memory
# If swap not active:
swapon /swapfile
```

---

## Scaling

To add more app instances, add `app3` to `docker-compose.yml` and update `nginx.conf` upstream block:
```nginx
upstream flask_app {
    server app1:8000;
    server app2:8000;
    server app3:8000;
}
```
Then: `docker compose up --build -d`

---

## Known Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Concurrent users | ~500 | Tested with k6, p95 2.38s |
| DB connections | 300 | PostgreSQL max_connections |
| Workers | 16 total | 8 per app container |
| RAM | 1GB + 1GB swap | DigitalOcean Basic Droplet |
| Redis TTL | 1 hour | Cached URL expiry |
