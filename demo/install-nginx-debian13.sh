#!/usr/bin/env bash
# =============================================================================
# WAF Platform demo — install the "Threat Library" nginx target on Debian 13
#
# Stands up a small nginx web app to sit BEHIND the WAF Management Platform.
# It serves the demo pages and answers the attack endpoints (/search, /download,
# /ping, /library, /api) with a canned 200 — so when the WAF blocks a request
# (403) you can clearly see it never reached the backend.
#
# Usage (as root, on a fresh Debian 13 box):
#   curl -fsSL https://raw.githubusercontent.com/socfortress/waf-platform-public/main/demo/install-nginx-debian13.sh | sudo bash
# or:
#   sudo bash install-nginx-debian13.sh
#
# Then register it in the WAF as a site with upstream http://host.docker.internal:8088
# (see demo/README.md).
# =============================================================================
set -euo pipefail

PORT="${DEMO_PORT:-8088}"
WEBROOT="/var/www/waf-demo"
REPO_RAW="https://raw.githubusercontent.com/socfortress/waf-platform-public/main/demo/site"
SITE_FILES=(index.html attack.html style.css)

err() { echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || err "run as root (use sudo)."
. /etc/os-release 2>/dev/null || true
echo "==> Detected: ${PRETTY_NAME:-unknown}"

echo "==> Installing nginx + curl ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx curl >/dev/null

echo "==> Fetching demo site files into ${WEBROOT} ..."
mkdir -p "$WEBROOT"
for f in "${SITE_FILES[@]}"; do
  curl -fsSL "${REPO_RAW}/${f}" -o "${WEBROOT}/${f}" || err "could not download ${f} from ${REPO_RAW}"
done

echo "==> Writing nginx site config (listening on :${PORT}) ..."
cat > /etc/nginx/sites-available/waf-demo <<NGINX
# Demo upstream for the WAF Management Platform.
# Listens on all interfaces so the WAF container can reach it via the Docker
# host gateway (http://host.docker.internal:${PORT}). A loopback-only bind
# (127.0.0.1) is NOT reachable from containers and causes a 502 at the WAF.
# This is a throwaway demo app with no secrets; to keep port ${PORT} off the
# public internet, restrict it with a firewall (see demo/README.md).
server {
    listen ${PORT} default_server;
    server_name _;
    root ${WEBROOT};
    index index.html;

    # Static pages (index.html, attack.html, style.css)
    location / {
        try_files \$uri \$uri/ =404;
    }

    # "Vulnerable" endpoints the attack console targets. nginx always answers
    # 200 here — so a 403 the caller sees came from the WAF, not the app.
    location = /search   { default_type application/json; return 200 '{"ok":true,"endpoint":"search","note":"reached backend"}'; }
    location = /library  { default_type application/json; return 200 '{"ok":true,"endpoint":"library","note":"reached backend"}'; }
    location = /download { default_type application/json; return 200 '{"ok":true,"endpoint":"download","note":"reached backend"}'; }
    location = /ping     { default_type application/json; return 200 '{"ok":true,"endpoint":"ping","note":"reached backend"}'; }
    location /api/       { default_type application/json; return 200 '{"ok":true,"endpoint":"api","note":"reached backend"}'; }
}
NGINX

ln -sf /etc/nginx/sites-available/waf-demo /etc/nginx/sites-enabled/waf-demo
rm -f /etc/nginx/sites-enabled/default

echo "==> Testing and reloading nginx ..."
nginx -t
systemctl enable nginx >/dev/null 2>&1 || true
systemctl restart nginx

echo ""
echo "============================================================"
echo " Demo target is up:  http://<host>:${PORT}/"
echo " Reachable from the WAF container as host.docker.internal:${PORT}"
echo "============================================================"
echo ""
echo "Next: register it in the WAF Management Platform as a site."
echo "  - Upstream URL : http://host.docker.internal:${PORT}"
echo "  - Hostname     : your demo domain (e.g. demo.example.com)"
echo "  - Cert mode    : letsencrypt   (Caddy auto-provisions TLS)"
echo "  - Detection    : OFF  (blocking mode)"
echo ""
echo "For the WAF's Caddy container to reach this host port, the caddy-waf"
echo "service needs 'host.docker.internal' mapped to the host gateway."
echo "The published docker-compose.yml already includes this. If you customized"
echo "it, ensure caddy-waf has:"
echo "    extra_hosts:"
echo "      - \"host.docker.internal:host-gateway\""
echo ""
echo "Then browse to https://<your-domain>/ and open the Attack Console."
