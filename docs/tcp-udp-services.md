# TCP/UDP forwarding

TCP/UDP Services forwards raw traffic through Caddy to one upstream per listener.
For example, `mail.example.com:993` can reach an IMAPS server while the same
hostname's HTTPS traffic continues through the existing web application firewall.

This feature provides **raw forwarding only**. Coraza, HTTP authentication,
HTTP rate limits, reputation, site IP ACLs and GeoIP blocking do not apply. TLS (including
STARTTLS) passes through unchanged; the upstream owns certificates and renewal.
There is no TLS termination, SNI routing, PROXY protocol, load balancing or
transparent source-IP preservation in this MVP. Upstreams normally see Caddy's
address. Check mail relay policies before putting an SMTP server behind a proxy.

## Upgrade and deployment

Use the prebuilt **1.0.32** images for Caddy, `waf-sandbox`, the admin API and UI.
No source build or private repository access is needed. Back up your database,
deployment settings and rules, and record the previous image versions first.
API startup applies the merged migrations and restores the HTTP/TCP/UDP config.
An older Caddy image will reject enabled stream configurations because it lacks
the `layer4` module. The published image includes caddy-l4 v0.1.1 alongside
Caddy 2.11.4, coraza-caddy 2.6.2 and Coraza 3.8.1.

The migration head is `0037_merge_forwarding_reputation`. It joins the released
reputation history with forwarding and compatible policy migration histories. All revision IDs remain intact; `alembic upgrade head` applies any missing
branches without restamping. The compatibility `sites.ai_review` column defaults
to `{}` and is unused by this release; it does not enable AI review.

Docker ports must be explicitly published by the operator. Saving a service in
the UI does **not** change Docker, the host firewall, cloud security groups, or
router port forwarding. The API does not need access to the Docker socket.

1. Update your public deployment checkout with `git pull --ff-only`. Set
   `WAF_IMAGE_TAG=1.0.32` (no leading `v`) in `.env`. Remove obsolete hotfix image
   or `pull_policy: never` overrides for the platform images while preserving
   your other customizations. Copy `docker-compose.streams.example.yml` to
   `docker-compose.streams.yml`.
2. Edit the override to expose only the required ports. For example:

   ```yaml
   services:
     caddy-waf:
       ports:
         - "993:993/tcp"
         - "10000:10000/udp"
   ```

   Each mapping is `HOST_PORT:CONTAINER_PORT/PROTOCOL`. The service's listen port
   is the **container** port. TCP and UDP require separate mappings, even when
   their port numbers match. To restrict a host interface, use a mapping such as
   `192.0.2.10:993:993/tcp` with your host's actual address. Unqualified mappings
   expose the port on all host interfaces. Existing 80/443 mappings are retained.

3. Review and deploy the merged configuration:

   ```sh
   docker compose -f docker-compose.yml -f docker-compose.streams.yml config --images
   docker compose -f docker-compose.yml -f docker-compose.streams.yml pull
   docker compose -f docker-compose.yml -f docker-compose.streams.yml up -d --wait
   docker compose -f docker-compose.yml -f docker-compose.streams.yml restart admin-api
   ```

   Restarting the API **after Caddy is ready** ensures that saved listeners are
   pushed again, including when only Caddy was recreated. The current platform
   restores generated configuration at API startup; Caddy alone starts from its
   bootstrap Caddyfile. The restart step can briefly interrupt management access.

4. Open **TCP/UDP Services → Add service**. Enter a name, protocol, listen address
   and port, upstream host and port, and enable the service. Test it from another
   machine using a client for that protocol.

Use the same override with subsequent Compose commands. When changing published
ports, recreate Caddy with `up -d` and then restart the API; `docker compose restart`
alone does not update Docker port mappings. Deleting a service removes its Caddy
listener but does not remove its Docker mapping. Remove unused mappings explicitly.

## Listener and upstream rules

- A listen address belongs to the **Caddy container**, not the Docker host.
  `0.0.0.0` is the default for Docker IPv4 publishing. Custom IPv4/IPv6 addresses
  must exist inside the container; IPv6 also requires suitable Docker networking.
- The MVP reserves each `(protocol, listen port)` pair across all bind addresses,
  even for disabled services. Edit or delete the existing entry to reuse it.
  TCP and UDP may share the same numeric port.
- Container ports 80, 443 and 2019 are reserved for HTTP/HTTPS and Caddy's admin
  API. Host TCP 8443 is used by the default management UI; host 22 may be occupied
  by SSH. Choose another host port or deliberately move the conflicting service.
- Upstream hosts accept DNS names and IPv4/IPv6 addresses, without URL schemes,
  paths or ports. Enter IPv6 without brackets; the config generator adds them.
  DNS names must resolve from Caddy. `localhost` refers to Caddy's container.
- UDP associations use the pinned module's default 30-second idle timeout.
- Protocols with additional negotiated ports, such as FTP, need those ports
  configured too. Generic forwarding is not an FTP-aware gateway.

## Permissions, state and diagnostics

Admins and superadmins can create, edit, enable/disable and delete services.
Viewers can list them; operators have no stream access. Service tokens inherit
their owner's stream permissions. Changes are recorded in the audit log.

“Enabled” means the listener is included in the saved configuration. It is not a
health check or evidence that a host port is published. Invalid configurations
are rejected without committing the service change. Caddy retains its previous
configuration when it rejects a load. Full config reloads are serialized through
a PostgreSQL transaction advisory lock so an unrelated site edit cannot erase a
newly saved listener. Startup and the config preview also include stream services.

Review connection errors with:

```sh
docker compose -f docker-compose.yml -f docker-compose.streams.yml logs --tail=100 caddy-waf
```

L4 errors use Caddy's runtime logs, not the HTTP WAF event viewer. If a connection
fails, check the saved listener, exact TCP/UDP mapping, host firewall and upstream
reachability. Long-lived connections may outlast configuration changes; disabling
or deleting a listener is not a promise to terminate every existing session.

## API

- `GET /api/v1/stream-services/` — list (`streams:read`).
- `POST /api/v1/stream-services/` — create (`streams:write`).
- `PUT /api/v1/stream-services/{id}` — replace/edit, including enable/disable (`streams:write`).
- `DELETE /api/v1/stream-services/{id}` — delete (`streams:delete`).

Example create/replace body:

```json
{
  "name": "Mail IMAPS",
  "protocol": "tcp",
  "listen_address": "0.0.0.0",
  "listen_port": 993,
  "upstream_host": "mail.internal.example",
  "upstream_port": 993,
  "is_enabled": true
}
```

Conflict responses use HTTP 409; invalid input or a rejected Caddy configuration
uses HTTP 422. No endpoint automatically publishes ports or probes upstreams.

## Rollback

Disable or remove raw listeners, remove their Docker port mappings, and recreate
Caddy. Restore all previous platform image versions together and restart the
previous API after Caddy is ready. Keep the data volumes. The added schema can
remain; do not blindly downgrade the merged migrations, which would remove
stored services and policies.
