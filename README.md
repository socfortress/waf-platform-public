# WAF Management Platform

Self-hosted Web Application Firewall with a modern admin UI. Powered by
**Caddy + Coraza** (OWASP Core Rule Set v4) as the WAF engine, a **FastAPI**
management API, and a **React** dashboard.

This repository contains everything you need to **run** the platform from
prebuilt container images — no source build required.

## New release: v1.0.42 — update notifications

[v1.0.42](https://github.com/socfortress/waf-platform-public/releases/tag/v1.0.42)
lets the admin UI tell you when a newer WAF release is available: admins see a
banner after signing in, and the About page shows the latest release. The admin
API checks this repository's releases at most once every 6 hours; set
`UPDATE_CHECK_ENABLED=false` on hosts without internet access. There are no
database migrations or Compose changes.

Read the [upgrade notes](docs/releases/v1.0.42.md) and update both the image tag
and Caddy digest. Upgrading from v1.0.40 or older? Also review the
[v1.0.41 security release](docs/releases/v1.0.41.md), which changed per-site JWT
audience handling and exclusion regex validation, and the
[v1.0.40 notes](docs/releases/v1.0.40.md), including its certificate-storage
migration. Older installations must also review the
[v1.0.39 path ACL changes](docs/releases/v1.0.39.md) and
[v1.0.37 prerequisites](docs/releases/v1.0.37.md).

ACL labels and country allowlists ([v1.0.40](docs/releases/v1.0.40.md)),
hostname aliases, upstream identity controls, backend pools,
[TCP/UDP forwarding](docs/tcp-udp-services.md), and the optional
[PHP2Shell mitigation pack](rule-packs/php2shell/README.md) remain available.
Experimental [NTLM compatibility](docs/ntlm-compatibility.md) retains its existing limits.

To receive future release notifications, use **Watch → Custom → Releases** on
[this public repository](https://github.com/socfortress/waf-platform-public),
or subscribe to the [releases feed](https://github.com/socfortress/waf-platform-public/releases.atom).
No private repository access is needed.

## 📺 Watch the demo

Deploy the WAF, get automatic TLS, block live attacks, and tune a false positive — in about 10 minutes:

[![Watch the demo on YouTube](https://img.youtube.com/vi/ZvjfPXP3X30/maxresdefault.jpg)](https://youtu.be/ZvjfPXP3X30)

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
- **IP reputation feeds** — import public or licensed IP/CIDR lists, inspect saved entries, and choose Off, Observe, or Block per site. Lookups run locally in Caddy.

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

Optional — pin a version: set `WAF_IMAGE_TAG` to a version number from [Releases](https://github.com/socfortress/waf-platform-public/releases), without the `v` prefix (e.g. `1.0.33` for release `v1.0.33`), instead of `latest`.

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

## Protecting your app

A fresh install has **no sites configured** — Caddy listens on 80/443 but does
not proxy anything yet (a bare request to `http://localhost/` returns an empty
`200`). You configure protection from the admin UI:

1. Log in (see above) and add your upstream application as a **site**.
2. Choose **detection** mode (log only) or **blocking** mode (reject attacks).
3. The WAF then proxies and protects that site.

### Optional: verify against the bundled test upstream

The stack includes a throwaway `http-echo` container you can use as a target.
Add a test site in **blocking** mode pointing at `http-echo:5678`, then:

```bash
curl http://localhost/                                       # → upstream-ok
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost/?id=1+OR+1%3D1"   # → 403 (SQLi blocked)
```

A benign request returns `200`; the SQLi probe returns `403` once the site is in
blocking mode.

---

## IP reputation feeds (1.0.27 and later)

After updating both this Compose file and the application images, open **IP Reputation** in the admin UI. Add a public HTTPS IP/CIDR list or use a source preset, refresh it, then inspect the saved entries with **View IPs**. On each protected site, start with **Observe** to check matches in Caddy access logs; switch to **Block** when ready. Matched requests then receive HTTP 403. You can also set site-specific IP/CIDR exceptions. The feed snapshot is shared between the admin API and Caddy through the `reputation-data` volume, so requests do not wait for a feed provider.

- **Spamhaus DROP IPv4/IPv6:** public presets that need no account or API key. They refresh at most once every 24 hours and start disabled. Review [Spamhaus's DROP fair-use terms](https://www.spamhaus.org/blocklists/drop-fair-use-policy/) for your use.
- **CrowdSec raw IP list:** create a Raw IP List integration in CrowdSec Console, subscribe it to the blocklists available on your plan, and enter its integration URL plus the one-time username and password. The preset refreshes daily. A CrowdSec API key from a Remediation Component integration is a different credential and does not belong in the Basic Auth fields.
- **Other providers:** HTTPS downloadable line lists or JSON lists can be added with an optional `Authorization` or `X-*` header. Follow each provider's license and rate limits. Query-only reputation APIs are not supported by this release.

Configure **WAF Config → Trusted proxy IPs** if a load balancer or CDN connects directly to Caddy, so the reputation lookup uses the real client IP. Feed failures keep the last good entries only until their stale deadline; expired entries stop matching. Reputation matches appear in **Caddy access logs**; pre-Coraza blocks do not yet appear in the platform's WAF Logs or alerts. See [IP reputation setup and limits](docs/ip-reputation.md).

---

## Updating

Read the [public release notes](https://github.com/socfortress/waf-platform-public/releases/latest)
for compatibility changes and back up your database, rules and deployment settings.
Update the deployment files with `git pull --ff-only`, preserving local customizations.
Set `WAF_IMAGE_TAG` in `.env` to the desired release without its `v` prefix;
`latest` follows new image publications. For managed CRS activation, also update
`CRS_CADDY_DIGEST` to the Caddy digest in that release's notes. A digest pin takes
precedence over a tag: changing only the tag leaves Caddy on its previous digest.
Upgrade Caddy, the sandbox, API and UI together.

Before recreating a deployment that lacks certificate storage mounts, follow
[the certificate persistence migration](#persisting-caddy-certificates-when-upgrading).

For v1.0.40, follow the ordered [upgrade steps](docs/releases/v1.0.40.md), including
starting Caddy before the API synchronizes the saved configuration.

```bash
docker compose pull        # fetch the latest images (or your pinned WAF_IMAGE_TAG)
docker compose up -d        # recreate changed containers
```

Your data (Postgres, Redis, rules, certs, reputation snapshots) lives in named Docker volumes and
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
- **Issues / questions:** open an issue on this repository
- Commercial support is available from [SOCFortress](https://www.socfortress.co/solutions/professional-services).

## Persisting Caddy certificates when upgrading

The shipped Compose files mount `caddy-data` at `/data` for ACME accounts,
certificates and keys, and `caddy-runtime-config` at `/config` for Caddy runtime
state. These volumes belong only to production Caddy, not the validator or API.
`caddy-config:/etc/caddy` contains configuration files and is not certificate
storage. Confirmed-boot configuration remains authoritative; persisting an
autosave does not enable `--resume` or bypass CRS recovery checks.

**Existing installations must copy their old container's state before recreating
it with these mounts.** An empty mount hides the old writable layer. Do not run
`docker compose down`, recreate Caddy, or remove the old container first. A helper
using only `--volumes-from` cannot back up unmounted writable-layer directories.
If the original container is already gone, recover certificates from a trusted
backup; repeated issuance attempts can hit CA rate limits.

During a maintenance window, stop configuration edits and follow these steps
from your existing Compose directory, preserving its project name and overrides:

```sh
set -eu
umask 077
persist_backup="$PWD/.waf-backups/caddy-persistence-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$persist_backup"
cp -p docker-compose.yml .env "$persist_backup/"
# Also preserve any Compose override files and the normal database/CRS backups.
docker compose stop admin-ui admin-api caddy-waf waf-sandbox
docker cp caddy-waf:/data "$persist_backup/data"
docker cp caddy-waf:/config "$persist_backup/config"
test -d "$persist_backup/data/caddy"
```

Verify the backup contains your expected certificate/account files. It contains
private keys: keep it private and do not attach it to issues. Keep the old
container stopped until the copy is verified. If the copy fails, leave the
container in place and restart the existing deployment while investigating.

Now apply the updated Compose definitions (or add these two mounts and volume
declarations to your customized file). If you already persist these directories,
retain the existing volume names/bind paths; do not switch to empty volumes.
For example, externally managed lab volumes should retain their `external: true`
and explicit `name` settings. For the source-build installation, build the new
Caddy image before creating its replacement; public deployments use the matching
published image pins. Then restore into the stopped replacement:

```sh
docker compose config --quiet
docker compose create caddy-waf
docker cp "$persist_backup/data/." caddy-waf:/data
docker cp "$persist_backup/config/." caddy-waf:/config
persist_image=$(docker inspect --format '{{.Image}}' caddy-waf)
docker run --rm --network none --user 0 --volumes-from caddy-waf \
  --entrypoint sh "$persist_image" -ec \
  'chown -R "$(id -u caddy):$(id -g caddy)" /data /config; chmod 700 /data /config'
docker compose up -d --no-deps --wait caddy-waf waf-sandbox
docker compose up -d --no-deps --wait admin-api admin-ui
```

The ownership step accounts for `docker cp` creating root-owned files. New empty
volumes in freshly built images inherit Caddy ownership and private directory
permissions. Check HTTPS with certificate verification enabled, confirm expected
certificate identity, and confirm API/CRS synchronization. Back up both new
volumes alongside the database, confirmed configuration, CRS and imported
certificates. Do not delete them with `down -v` or volume pruning when upgrading.
Custom storage backends or `XDG_DATA_HOME`/`XDG_CONFIG_HOME` overrides need matching
backup and mount paths rather than the default commands above.

References: [Caddy storage conventions](https://caddyserver.com/docs/conventions#data-directory)
and [Docker copy behavior](https://docs.docker.com/reference/cli/docker/container/cp/).
