# WAF Management Platform

Self-hosted Web Application Firewall with a modern admin UI. Powered by
**Caddy + Coraza** (OWASP Core Rule Set v4) as the WAF engine, a **FastAPI**
management API, and a **React** dashboard.

This repository contains everything you need to **run** the platform from
prebuilt container images — no source build required.

---

## Architecture

```
        Internet
           │
           ▼
  ┌─────────────────────┐      ┌──────────────────────────┐
  │  Caddy + Coraza      │ ───► │  Your protected upstream │
  │  WAF engine (80/443) │      │  app(s)                  │
  └─────────────────────┘      └──────────────────────────┘
           ▲  (Admin API 2019, container-internal only)
           │
  ┌─────────────────────┐   ┌────────────┐   ┌─────────┐
  │  FastAPI Admin API   │ ◄─►│ PostgreSQL │   │  Redis  │
  │  (8000, internal)    │   └────────────┘   └─────────┘
  └─────────────────────┘
           ▲
           │
  ┌─────────────────────┐
  │  React Admin UI      │   ← you log in here: https://localhost:8443
  │  (Nginx, 8443 HTTPS) │
  └─────────────────────┘
```

---

## Features

- **Caddy + Coraza WAF** with the OWASP Core Rule Set v4, in detection or blocking mode per site.
- **Site management** — front any number of upstream apps behind the WAF.
- **CRS & custom rules** — tune the ruleset, add custom rules, manage false-positive exclusions from the UI.
- **Authentication** with TOTP 2FA and role-based access control.
- **Log viewer** — searchable, PostgreSQL-backed request/blocking logs with GeoIP enrichment.
- **Alerting** — email notifications on configurable conditions.

---

## Quick start

### Prerequisites

- Docker ≥ 24 and Docker Compose ≥ 2.20
- 2 GB RAM minimum
- Ports **80**, **443**, and **8443** available on the host
- A free **MaxMind GeoLite2** license key (see [GeoIP setup](#geoip-setup))

### 1. Get this repo

```bash
git clone https://github.com/socfortress/waf-platform-public.git waf-platform
cd waf-platform
cp .env.example .env
```

### 2. Configure `.env`

Edit `.env` and replace every `CHANGE_ME` value:

| Variable | Purpose | How to generate |
|---|---|---|
| `POSTGRES_PASSWORD` | Database password | `openssl rand -hex 32` |
| `SECRET_KEY` | JWT signing key | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `TOTP_ENCRYPTION_KEY` | TOTP secret encryption | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BOOTSTRAP_ADMIN_EMAIL` | First superadmin email | Any valid email |
| `BOOTSTRAP_ADMIN_PASSWORD` | First superadmin password | Strong password — **change after first login** |
| `ALLOWED_ORIGINS` | CORS origins | `https://localhost:8443` for the default local deploy |

Optional — email alerts: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

Optional — pin a version: set `WAF_IMAGE_TAG` to a release tag (e.g. `v1.0.0`) instead of `latest`.

### 3. GeoIP setup

The log viewer enriches client IPs with country/city data using MaxMind's
GeoLite2 database. MaxMind's license does not allow us to redistribute it, so
you supply your own (it's free):

1. Create a free account at <https://www.maxmind.com/en/geolite2/signup>.
2. Download **GeoLite2 City** (`.mmdb` format).
3. Place the file in this directory as `GeoLite2-City.mmdb`, **or** set
   `GEOIP_DB_PATH` in `.env` to its full path.

> The stack will start without it, but GeoIP enrichment in logs will be disabled.

### 4. Start the stack

```bash
docker compose up -d
```

Wait until all containers report healthy (typically 30–60 seconds):

```bash
docker compose ps
```

### 5. First login

1. Open **https://localhost:8443** (the UI uses a self-signed certificate on
   first boot — accept the browser warning, or upload your own cert in the UI).
2. Log in with the `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` from `.env`.
3. **Change your password immediately** via Users → Edit.
4. Optionally enroll TOTP under Settings → Security.

---

## Protecting your own app

By default the WAF proxies a dummy `http-echo` upstream so you can verify the
stack end-to-end. To protect a real application, add it as a site in the admin
UI and point the WAF at your upstream. See the in-app Operations guidance for
details.

Verify the WAF is live:

```bash
curl http://localhost/                                   # → upstream-ok
curl -s -o /dev/null -w "%{http_code}" "http://localhost/?id=1+OR+1%3D1"   # → 403 (SQLi blocked)
```

---

## Updating

```bash
docker compose pull        # fetch the latest images (or your pinned WAF_IMAGE_TAG)
docker compose up -d        # recreate changed containers
```

Your data (Postgres, Redis, rules, certs) lives in named Docker volumes and
survives updates.

---

## Managing the stack

```bash
docker compose ps           # status
docker compose logs -f      # follow logs
docker compose down         # stop (volumes preserved)
docker compose down -v      # stop AND delete all data volumes — destructive
```

---

## Security notes

- Passwords are bcrypt-hashed; TOTP secrets are encrypted at rest.
- Secrets are read from environment variables only — never hardcoded. Keep `.env` private.
- The Caddy Admin API (port 2019) is bound inside the Docker network only; it is not exposed to the host.
- CORS is restricted to `ALLOWED_ORIGINS` — no wildcard.
- Auth endpoints are rate-limited; refresh tokens rotate on every use.
- For production, place the UI behind your own TLS termination / trusted certificate rather than the self-signed default.

---

## Support & licensing

- **License:** see [LICENSE](LICENSE).
- **Issues / questions:** open an issue on this repository.
- Commercial support is available from [SOCFortress](https://www.socfortress.co).
