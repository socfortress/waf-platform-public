# IP reputation feeds

IP reputation is optional and configured per protected site. The admin API downloads and normalizes feeds, then publishes a snapshot to the shared `reputation-data` volume. Caddy checks a local index on each request. No request waits for an external feed or the admin API.

## Set up a feed

1. Open **IP Reputation** in the admin UI. Add a public HTTPS endpoint on port 443, or choose a source preset. Feeds begin disabled. Enable the source and use **Refresh** to verify its status and entry count.
2. For a generic feed, choose `lines` (one public IPv4/IPv6 address or CIDR per line, with `#` or `;` comments) or `json` (an array of addresses, or an `entries` array containing objects with `ip` or `network`, and optional `reason` and `expires_at`). If needed, add an `Authorization` or `X-*` header. Credentials are encrypted in the database and excluded from the Caddy snapshot and API responses.
3. Choose a refresh interval permitted by your provider and a maximum stale age at least twice that interval. Manual refreshes respect the interval. An HTTP 429 retains the last successful list only until its stale deadline. Use **View IPs** to browse or search saved IPs, CIDRs, and reasons without another download.
4. On each site, select **Observe** and review matches in Caddy access logs. Add narrow IP/CIDR exceptions if needed, then select **Block** to return HTTP 403 for matches. **Off** disables reputation for that site. The mode applies to every enabled, unexpired source.
5. If a load balancer or CDN connects directly to Caddy, set its addresses under **WAF Config → Trusted proxy IPs**. This lets Caddy determine the client IP from forwarded headers. Only add proxies you control.

## Source presets

**Spamhaus DROP IPv4/IPv6:** These public lists need no account or API key. Each preset starts disabled, refreshes no more than once per 24 hours, and stops matching after two days without fresh data. DROP identifies a focused set of high-risk network ranges, not a general real-time reputation service. Follow the [DROP fair-use terms](https://www.spamhaus.org/blocklists/drop-fair-use-policy/); other Spamhaus datasets have separate access terms.

**CrowdSec raw IP list:** In CrowdSec Console, create a Raw IP List integration and subscribe it to blocklists available on your plan. Copy its integration URL and one-time username and password into **Set up CrowdSec raw list**. The form adds `/content` when needed and builds the Basic Auth header. The preset refreshes daily to respect the Community plan's one-pull-per-24-hours limit. A Remediation Component integration provides an API key instead; that key does not work in these Basic Auth fields. The Community Blocklist has separate Security Engine requirements.

## Limits and failure behavior

Generic feeds must be public HTTPS endpoints on port 443, without redirects or query-string tokens. Downloads are limited to 16 MiB and 100,000 entries per source; the combined snapshot is limited to 500,000 entries or 64 MiB. Generic CIDRs broader than IPv4 /16 or IPv6 /32 are rejected. Query-only reputation APIs require a separate integration and are not supported here.

Successful downloads replace that source's entries. A valid empty response clears them. Expired entries and stale sources stop matching even if the last snapshot remains on disk. A missing snapshot lets requests continue through the normal WAF path. Feed changes do not reload Caddy.

Matches are attributed in Caddy access logs with source, matching address/range, reason, mode, and site. Reputation blocks occur before Coraza and are not yet ingested into the platform's WAF Logs, alerts, or forwarders. No feed or CrowdSec account is enabled automatically.

Provider documentation: [CrowdSec Raw IP List](https://docs.crowdsec.net/u/integrations/rawiplist/) and [Spamhaus DROP](https://www.spamhaus.org/faqs/do-not-route-or-peer-drop/).
