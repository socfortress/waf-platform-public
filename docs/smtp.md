# SMTP alert configuration

Set SMTP_HOST and SMTP_FROM in `.env`, and configure the recipient in Alerts → Channels.


`SMTP_SECURITY` explicitly selects the transport. The port is configured separately
with `SMTP_PORT` (default `587`); changing the port does not select encryption.

| Mode | Behavior | Typical port |
|---|---|---|
| `starttls` (default) | Connects, then requires a successful STARTTLS upgrade before authentication or message delivery | 587 or 25 |
| `tls` | Establishes TLS immediately on connection (implicit TLS) | 465 |
| `none` | Sends without transport encryption; only use for an explicitly trusted relay connection | 25 |

TLS modes validate the server certificate, including hostname and trust chain.
Unsupported STARTTLS, certificate errors, and TLS negotiation failures cause delivery
to fail; there is no plaintext fallback. Channel test failures include the SMTP error.
There is no certificate-verification bypass setting.

Authentication is independent of the security mode. Set both `SMTP_USER` and
`SMTP_PASSWORD` for password authentication, or leave both empty to skip SMTP AUTH
when your relay permits it. An incomplete credential pair or invalid security mode
prevents the application from starting. The `none` mode also leaves any configured
authentication credentials unprotected; use a TLS mode for authenticated submission.
Client-certificate authentication is not currently configurable.

Authenticated STARTTLS submission:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=waf@example.com
SMTP_PASSWORD=replace-with-provider-password
SMTP_FROM=waf@example.com
```

For implicit TLS, use the same credentials and sender with `SMTP_PORT=465` and
`SMTP_SECURITY=tls`.

An unauthenticated relay with mandatory STARTTLS:

```dotenv
SMTP_HOST=relay.example.com
SMTP_PORT=25
SMTP_SECURITY=starttls
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=waf@example.com
```

For a relay that deliberately uses plaintext, explicitly change the above to
`SMTP_SECURITY=none`.

For a private CA, set `SMTP_CA_BUNDLE` to a readable PEM CA bundle **inside the
admin-api container**, for example `/etc/smtp/ca.pem`, and mount it read-only using
a Compose override:

```yaml
services:
  admin-api:
    volumes:
      - ./smtp-ca.pem:/etc/smtp/ca.pem:ro
```

Leave `SMTP_CA_BUNDLE` empty to use the default trusted CAs. A custom bundle adds
trusted CAs for SMTP; include the necessary private CA certificates. The server hostname
must still match its certificate. No client private key is needed for this setting.

After changing `.env` or mounts, recreate the API container with
`docker compose up -d --force-recreate admin-api`, then test the email channel.

**Upgrade note:** previously, leaving `SMTP_USER` empty disabled STARTTLS. The new
default requires STARTTLS even without credentials. Existing unauthenticated
plaintext relays must explicitly set `SMTP_SECURITY=none`, or enable STARTTLS on
the relay. Existing authenticated STARTTLS configurations keep their behavior.

