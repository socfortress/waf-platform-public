# WAF Platform — Live Demo

A self-contained demo that puts a small web app ("SOC Threat Library") **behind**
the WAF Management Platform, then lets you fire real web attacks at it and watch
the WAF block them — and fix a false positive live with a scoped exclusion.

```
  Browser ──HTTPS──► WAF (Caddy + Coraza + OWASP CRS) ──► nginx demo app
                     auto TLS · blocks attacks · logs           (loopback only)
```

The app is only reachable **through** the WAF, so every request — including the
attack console's own requests — is inspected first.

---

## What's here

| File | Purpose |
|---|---|
| `install-nginx-debian13.sh` | One command to stand up the nginx demo target on Debian 13 |
| `site/index.html` | The demo app: a knowledge-base search (used for the false-positive demo) |
| `site/attack.html` | Attack Console — buttons that fire SQLi / XSS / LFI / RCE / RFI at the app |
| `site/style.css` | Styling |

---

## Prerequisites

- The WAF platform running (see the repo root `README.md`) — `docker compose up -d`.
- A Debian 13 host (can be the **same** box as the WAF).
- For real Let's Encrypt TLS: a public domain's DNS A record pointing at the host,
  with ports **80** and **443** reachable from the internet. (No public domain?
  See *Local-only variant* at the bottom.)

---

## 1. Install the demo target

On the Debian 13 host:

```bash
curl -fsSL https://raw.githubusercontent.com/socfortress/waf-platform-public/main/demo/install-nginx-debian13.sh | sudo bash
```

This installs nginx, drops the demo pages in `/var/www/waf-demo`, and listens on
`127.0.0.1:8088` (loopback only — the app has no public exposure of its own).

## 2. Register it as a site in the WAF UI

Log into the WAF UI (`https://<host>:8443`) → **Sites → Add site**:

| Field | Value |
|---|---|
| Name | `Threat Library` |
| Upstream URL | `http://host.docker.internal:8088` |
| Hostname | `demo.example.com` (your domain) |
| Cert mode | **Let's Encrypt** |
| Detection-only | **off** (blocking mode) |

Caddy provisions the TLS certificate automatically — no cert files, no renewals.
The published `docker-compose.yml` already maps `host.docker.internal` so the WAF
container can reach the host's nginx.

## 3. See the WAF in action

Browse to **`https://demo.example.com/`** (note the auto-provisioned padlock),
then open the **Attack Console**:

- **Run all attacks** → every payload comes back **BLOCKED (403)**.
- The two **Normal search** buttons come back **ALLOWED (200)** — real users aren't affected.

Open the platform's **Logs** view alongside it: each block appears with its
triggered **rule ID**, attack category, client IP, and GeoIP country — live.

## 4. Fix a false positive with an exclusion

Click **Analyst IOC lookup** in the Attack Console (or search
`powershell -enc base64 payload` in the app). It's **blocked** — but for a SOC
analyst, looking up a PowerShell indicator in the knowledge base is legitimate.
Fix it without weakening protection elsewhere:

1. In **Logs**, find the blocked `/library?term=...` request and note its rule ID
   — here it's **932120** (Windows PowerShell command detection).
2. Go to **Rules → CRS Rules**, find rule `932120`, and add an **exclusion**
   targeting `ARGS:term` (the knowledge-base search parameter).
3. Re-run **Analyst IOC lookup** → now **ALLOWED (200)**.

Because the exclusion is scoped to the `term` parameter, the **same** indicator
sent as an actual attack to a different endpoint (`/ping?host=powershell…`) is
**still blocked**, and unrelated rules (SQLi, XSS, traversal) are untouched.
That's the whole point: tune one false positive without opening a hole.

> Tip for choosing a demo false positive: the platform adds hardwired
> libinjection deny rules (`9000001` SQLi, `9000002` XSS) on top of CRS that
> bypass anomaly scoring, so a classic `' OR 1=1` string can't be cleared with a
> CRS exclusion. Pick a payload blocked by a single excludable CRS rule (like the
> PowerShell IOC → `932120`) for a clean live fix.

---

## Header-based attacks (run from a terminal)

Browser JavaScript can't set headers like `User-Agent`, so run these with `curl`
to exercise scanner/protocol rules:

```bash
DOMAIN=https://demo.example.com

# Scanner User-Agent (CRS 913xxx)
curl -s -o /dev/null -w "%{http_code}\n" -A "sqlmap/1.7" "$DOMAIN/"

# SQLi in a query string (CRS 942xxx)
curl -s -o /dev/null -w "%{http_code}\n" "$DOMAIN/search?q=1%27%20OR%20%271%27%3D%271"

# Path traversal (CRS 930xxx)
curl -s -o /dev/null -w "%{http_code}\n" "$DOMAIN/download?file=../../../../etc/passwd"

# Log4Shell-style header (CRS 944xxx)
curl -s -o /dev/null -w "%{http_code}\n" -H 'X-Api: ${jndi:ldap://x/a}' "$DOMAIN/"
```

Each should print `403` while the site is in blocking mode.

---

## Detection vs blocking (good for the demo)

Flip the site to **Detection-only** and re-run the attacks: they now return `200`
(reached the backend) but still appear in **Logs** as `detected`. This shows how
you can roll out the WAF in monitor mode, review what *would* be blocked, then
switch to blocking once you've tuned exclusions.

---

## Troubleshooting

**WAF returns 502, logs show `dial tcp 172.17.0.1:8088: connect: connection refused`.**
nginx isn't listening on an interface the WAF container can reach. It must bind
all interfaces (`listen 8088;`), not loopback (`listen 127.0.0.1:8088;`) — the
host's loopback is not reachable from containers. Fix and reload:
```bash
sudo sed -i 's/listen 127.0.0.1:8088/listen 8088/' /etc/nginx/sites-available/waf-demo
sudo nginx -t && sudo systemctl reload nginx
curl -s -o /dev/null -w "%{http_code}\n" http://172.17.0.1:8088/   # expect 200
```

**Keep port 8088 private (optional).** The demo app holds no secrets, but if you
don't want it reachable from the internet, allow only the Docker bridge to reach
it (do not enable a firewall without first allowing SSH):
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 8443/tcp
sudo ufw allow from 172.16.0.0/12 to any port 8088 proto tcp
sudo ufw --force enable
```

## Local-only variant (no public domain)

Without a public domain you can't get a real Let's Encrypt cert. Two options:

- **Manual cert mode** — generate a self-signed cert and upload it when adding the
  site (`cert_mode: manual`). The browser will warn; the WAF still works.
- **Plain HTTP** — set the site's hostname to your host/IP and `cert_mode: none`,
  and browse over `http://`. Fine for a local attack demo, just no TLS story.
