# Sentinel Deployment Guide

This guide keeps the deployment path generic and Docker-friendly so you can use it on any VM, container platform, or internal company environment.

## Production Checklist

- Use a strong `SECRET_KEY`.
- Set `SESSION_COOKIE_SECURE=true` behind HTTPS.
- Use a production MySQL instance instead of local development MySQL.
- Terminate HTTPS at your reverse proxy or platform edge.
- Keep the seeded demo admin only for demo environments. Replace it for real deployments.

## Required Environment Variables

```env
FLASK_ENV=production
SECRET_KEY=replace-with-a-long-random-secret
MYSQL_HOST=your-db-host
MYSQL_USER=your-db-user
MYSQL_PASSWORD=your-db-password
MYSQL_DB=secure_panel
SESSION_COOKIE_SECURE=true
SOCKETIO_ASYNC_MODE=eventlet
PORT=5000
RATELIMIT_ENABLED=true
GUNICORN_WORKER_CLASS=eventlet
```

## Fastest Docker-Based Deployment

### 1. Build the image

```bash
docker build -t sentinel-app .
```

### 2. Run a MySQL instance

Use any managed MySQL provider or your own MySQL container/VM.

### 3. Bootstrap the schema

Run `database.sql` once against the target database.

### 4. Run the app container

```bash
docker run \
  -p 5000:5000 \
  --env-file .env \
  sentinel-app
```

### 5. Put Nginx or a platform HTTPS proxy in front

Use the included Nginx config as a starting point:

- `nginx/default.conf`

## Docker Compose

For local or demo-server deployments, you can use:

```bash
docker compose up --build
```

The included compose file already starts:

- Flask app
- MySQL 8
- Nginx reverse proxy

## Recommended Hosting Shapes

Any of these patterns work well:

- one VM running Docker Compose
- container app service + managed MySQL
- Kubernetes deployment + managed MySQL

## Post-Deploy Smoke Test

After deployment, verify:

1. `/health` returns `{"status":"ok"}` when DB is reachable.
2. Guest users can open `/`.
3. Member registration/login works.
4. Member chat sends and receives messages in realtime.
5. Admin login redirects to `/admin`.
6. Admin can ban/unban users.
7. Admin cannot access member messages.

## Portfolio Tip

For recruiter-facing demos, deploy a stable demo instance and pair it with:

- a short README
- the preview visuals
- a 60-second demo walkthrough
- one screenshot of the member workspace
- one screenshot of the admin console

