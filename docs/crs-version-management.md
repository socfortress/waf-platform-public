# CRS version management

Phase 1 provides one active CRS bundle for all sites. Settings → OWASP Core Rule
Set offers pinned, LTS 4.25.x, and current CRS 4 tracks. A track changes the update
recommendation only. Installation and activation always require an administrator.

## Deployment prerequisites

This phase supports a single-host Compose deployment with POSIX shared-volume locks; multi-host replicas are outside its recovery contract.

Use the matching API, UI and Caddy images. Preserve the existing CRS and custom
rule volumes. Add a `config-state` volume at `/etc/coraza/config-state` to the API
(read/write) and production Caddy (read-only); the image creates it with owner
999, group 9001 and mode 2770. Set `CONFIG_STATE_ENABLED=true` for both services.
The API writes encrypted recovery snapshots and confirmed boot configuration here;
treat it as sensitive backup material along with the database and TLS files.

Use the existing `waf-sandbox` service, with the CRS volume read-only and no public
ports. Pin production Caddy and sandbox to the **same published image digest** in
Compose. In this public deployment, set `CRS_CADDY_DIGEST` to that digest,
including `sha256:`; Compose supplies `CRS_PRODUCTION_DIGEST` and
`CRS_VALIDATOR_DIGEST` to the API from that same value. Validate the resolved Compose images and container image
IDs during deployment. These fields are a deployment assertion, not remote
attestation; the API deliberately does not require Docker socket access.

Without these prerequisites, existing WAF traffic remains usable and the UI
reports why managed activation is unavailable. Missing validator/network access
must never silently skip validation.

For deployments using the public distribution repository, apply the same volume,
launcher/image, validator, and environment changes before enabling this feature.
This public Compose file contains the required mounts and maps `CRS_CADDY_DIGEST`
to both API digest declarations while pinning both Caddy image references. See
[the v1.0.37 release guide](releases/v1.0.37.md) for the exact digest and upgrade steps.

## Existing installations

1. Back up PostgreSQL, CRS, custom configuration/TLS, and config-state volumes.
2. Select **Snapshot existing rules**. This retains local bytes as an unverified
   baseline; it does not download or switch live rules.
3. Validate and explicitly activate that snapshot. This changes include paths to
   immutable bundle paths while retaining the existing content.
4. Select an update track and exact supported release. **Prepare release** checks
   its official detached GPG signature and archive layout before retaining it.
5. Validate the prepared bundle. Review added/removed rule IDs and overrides that
   refer to removed rules. Check the explicit acknowledgement and activate.

Customized or unidentifiable setup files are not automatically migrated. Keep the
existing deployment or move those settings to supported platform controls and
restore an identified stock setup before retrying. External includes, symlinks,
and external data dependencies require manual migration. A local snapshot is not
labelled an official signed release. Core-rule modifications remain in the old
bundle; they are not merged into a new official release.

Validation provisions every site's WAF policy in the isolated sandbox and runs
benign/attack checks with core CRS alone. It does not forward traffic to production
upstreams. This verifies compatibility, not absence of application false positives.
Production Caddy's load/readback is the final configuration check. Reports bind to
the active bundle and selection generation as well as site policy and engine;
changing the selection requires a new report before activation or rollback.

## Rollback

Select the retained previous ruleset, validate against **current site policies**,
review the report and choose **Roll back to selected version**. No download is
required. Site edits, hostname aliases, thresholds, and detection mode are not
reverted. Damaged/missing bundles are rejected during activation, explicit recovery,
and confirmed boot. The boot launcher checks referenced bundle identities and
complete file hashes before opening public listeners; its immutable admin-only
fallback lives outside the retained Caddy configuration volume.

Active/previous/local baseline bundles are retained. Phase 1 performs no automatic
bundle deletion. Keep rollback bundles and snapshots in backups. Do not manually
edit files below `managed/bundles`; hashes bind their identities.

## Recovery after an interrupted write

A shared filesystem writer lock is acquired before the PostgreSQL advisory lock, so a dropped database connection cannot immediately admit a second filesystem writer. Neither lock can cancel an already submitted Caddy request. If the API loses
contact during activation, writes remain blocked and runtime status is unconfirmed.
Do not repeatedly click Activate, delete the marker, or restart into raw autosave.
Caddy autosave may contain a candidate whose database transaction never committed.

For an ambiguous operation, an operator must:

1. Stop all old API executors/workers and ensure they have exited. Stop production
   Caddy to terminate any outstanding load request. Keep the persistent gate intact.
2. Start Caddy with `CONFIG_STATE_ENABLED=true` and
   `CONFIG_RECOVERY_ONLY=true` using its confirmed-boot launcher. This starts only
   the private admin endpoint, with no public proxy listeners. With this public
   Compose file, set `CONFIG_RECOVERY_ONLY=true` in `.env` and recreate Caddy
   with `docker compose up -d --force-recreate caddy-waf`.
3. Start one fresh API executor and confirm PostgreSQL is reachable. Ordinary
   startup synchronization is intentionally blocked while recovery is pending.
4. As an administrator, POST `/api/v1/settings/crs/recover` with
   `{"previous_executor_stopped":true}`. This is an attestation of step 1, not a
   command that stops old workers. The endpoint rejects a live public Caddy config
   and a matching old executor identity. It restores pre-write files if the DB
   transaction did not commit, loads the committed config, verifies readback and
   publishes confirmed boot state before unblocking writes.
5. Verify the selected version and runtime-confirmed status. Remove the temporary
   `CONFIG_RECOVERY_ONLY` override before a later normal Caddy restart.

This procedure can cause downtime. If database or file integrity cannot be
established, keep the admin-only state and investigate; do not bypass the gate.
A DB commit can succeed despite a lost response. The committed DB selection, not
the browser error message or raw autosave, determines recovery. Each managed write
has a transaction identity committed with the database and recorded in its pending
marker. This distinguishes committed file-only changes (including certificates at
unchanged paths) even when the Caddy JSON hash remains identical.

## API and operations

Use `/settings/crs/releases`, `/policy`, `/prepare`, `/adopt`,
`/bundles/{id}/validate`, `/activate`, `/rollback`, `/operations` and `/recover`
under `/api/v1`. Read access uses `config:read`; mutations use `config:write`.
Activation takes the bundle ID, expected generation, validation report ID,
acknowledgement and idempotency key. Stale validation must be repeated.

Preparation/validation are bounded request-driven operations with durable results,
not a new background deployment queue. The caller waits for completion. If the
connection drops, inspect history before retrying; never infer cancellation from
a timeout. An interrupted preparation can be retried with a new key because it
cannot affect active files. An interrupted activation requires reconciliation.
The old `/settings/crs/update` endpoint returns 410 and cannot bypass this flow.

Release discovery is cached and never activates rules. LTS support metadata is
reviewed with the platform; 4.25.x is supported upstream through Q3 2027. Network
errors show stale/unknown status rather than “up to date.”

Plugins, per-site CRS versions, and simultaneous shadow evaluation are outside
this phase.
