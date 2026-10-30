# NTLM upstream compatibility (experimental)

Enable **NTLM upstream compatibility** in a site's Backend section when the
application behind the WAF uses NTLM Windows authentication. The option defaults
to off. It passes authentication through to the backend; the WAF does not store
domain credentials or configure Active Directory, dashboard login, or Kerberos.

Use a single backend and direct client connections to the WAF. HTTPS is
recommended. NTLM sites advertise HTTP/1.1 over TLS and reject other HTTP versions
before proxying. Ordinary sites retain their existing protocol behavior.

Do not put a CDN or HTTP reverse proxy in front of an NTLM site. Such proxies can
reuse one connection for different users, which conflicts with connection-bound
authentication. Known forwarded headers and trusted proxy clients are rejected,
but a proxy that removes all such evidence cannot be detected. Backend pools,
failover, forward authentication, JWT and API-key authentication are rejected
with this option. No application retries are configured.

Existing upstream Host, TLS server name and certificate trust settings still
apply. Set those to the identities your application expects. WAF inspection and
site restrictions remain active, subject to the site's existing explicit bypass
rules. NTLM compatibility does not create a WAF bypass.

API: send `upstream_ntlm_enabled: true` when creating or updating a site. PATCH
omission preserves the current setting; `false` disables it. Clear an existing
pool with `backend_pool: null` in the same update before enabling NTLM. Migration
`0041_upstream_ntlm` initializes all existing sites to false. Deploy the updated
Caddy image with the API: older images lack the required transport and will
reject a configuration that enables this setting. A rejected apply follows the
platform's existing configuration recovery behavior.

Before reverting to a Caddy image without NTLM support, disable the affected sites
and confirm the configuration was applied. Re-enable them only with a compatible
transport: ordinary HTTP connection pooling is unsuitable for NTLM applications.

Only enable the setting on a test site first. Verify two different users and a
fresh anonymous session against the actual application, including reconnects,
uploads and your upstream TLS configuration. Windows/IIS browser SSO, Extended
Protection/channel binding, Kerberos, and production capacity remain unverified.
Do not weaken the application's authentication or TLS policy to make a test pass.

## Module verification

The release compiles `http.reverse_proxy.transport.http_ntlm` into Caddy:

```sh
docker exec caddy-waf caddy list-modules | grep http_ntlm
```

Enable the per-site setting after upgrading all platform images. Compiling the
module does not enable NTLM automatically. See the [release notes](releases/v1.0.38.md)
for validation evidence and known limitations.
