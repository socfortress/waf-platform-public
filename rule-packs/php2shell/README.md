# SOCFortress PHP2Shell mitigation pack 1.0.0

Distributed with [SOCFortress v1.0.31](https://github.com/socfortress/waf-platform-public/releases/tag/v1.0.31).
Install platform v1.0.30 or v1.0.31 (which includes the Coraza upgrade) first; this pack is an optional, manual
installation and is not enabled by pulling a platform image.

**Partial request-pattern mitigation for CVE-2026-109618 and CVE-2026-109619.
This pack does not patch PHP or establish protection against all PHP2Shell paths.**

Patch the PHP runtime serving your applications to 8.2.35, 8.3.36, 8.4.27,
8.5.12, or a vendor-confirmed fixed package, and restart its workers. Follow
the [PHP advisory](https://www.php.net/archive/2026.php#2026-10-21-5).

This directory is a publication package: source, example rules, an offline
generator, validation evidence, tests, and a redistribution license. It does not
install rules, change site settings, or contact a WAF API automatically.

## Choose a profile and check compatibility

| Profile | Intended use | Validation and recommendation |
| --- | --- | --- |
| `uploads` | Sites needing multipart forms/uploads, within the budgets below | Use SOCFortress **1.0.30** with Coraza **3.8.1**, coraza-caddy **2.6.2** and Caddy **2.11.4** (stock `waf` handler), or independently validate your build. **Not recommended on the tested SOCFortress 1.0.26 image / Coraza 3.7.0:** its parser accepts a truncated multipart fixture without setting the error flags used by this pack. |
| `strict` | PHP sites that do **not** need any multipart requests | Also validated on SOCFortress **1.0.26 / Coraza 3.7.0**, using its `waf` connector. It blocks multipart during phase 1, including legitimate multipart forms and uploads. Other coverage limits still apply. |

Check your actual engine with `docker compose exec caddy-waf caddy build-info`
and find `github.com/corazawaf/coraza/v3`. Image tags and source changes are not
evidence that a running deployment uses a particular engine. Upgrade using the
[1.0.30 release instructions](https://github.com/socfortress/waf-platform-public/releases/tag/v1.0.30)
before installing this optional pack. Exact tested image digests are in
[VALIDATION.md](VALIDATION.md).

## Rules and application impact

All deny rules match only the exact hostnames supplied to the generator. They
cover all paths on those hosts, including extensionless PHP routes, **except
earlier engine-off exceptions**. Host case, a trailing dot and an optional port
are handled. Add every hostname alias that can reach the application.

| Rule | Behavior | Application impact |
| --- | --- | --- |
| Duplicate Content-Type | Phase 1, HTTP 400 for multiple Content-Type headers | Rejects ambiguous request parsing |
| Incomplete/invalid body | Phase 2, HTTP 400 when `REQBODY_ERROR`, `MULTIPART_STRICT_ERROR` or `INBOUND_DATA_ERROR` is nonzero | Rejects malformed or partially inspected input **when the engine reports it** |
| Deep multipart name | HTTP 403 for 12 or more consecutive bracket components in a parsed multipart argument/file field name | May block deeply nested forms; not a complete PHP nesting-depth calculation |
| Multipart header budget | HTTP 403 above **100 total parsed multipart part-header lines** | Covers many empty files and header-heavy parts; legitimate batches also consume this budget |
| Decoded body budget | HTTP 413 above **8 MiB** of buffered request body, configurable | May block legitimate large API requests and uploads |
| Multipart disabled (`strict` only) | Phase 1 HTTP 403 for multipart/form-data | All multipart forms/uploads stop working |

The header budget is **not a 50-file limit**. Fifty file parts each carrying two
headers reach 100 lines; 51 exceed it. A part with only one header costs one,
while extra headers consume more. The rule counts parsed header entries, not
header bytes or necessarily every raw line PHP might accept.

Rules are independent and can be loaded in any order. This deliberately avoids
the two-rule file counter used by CrowdSec: the platform's custom-rule database
query does not guarantee order. No transaction counter, shared state, parser
override, AI decision, or anomaly-score threshold is required by this pack.

## Download and verify

Use this directory from the public repository, or download the standalone archive
and its SHA-256 file from the [public v1.0.31 release](https://github.com/socfortress/waf-platform-public/releases/tag/v1.0.31).
Neither route requires access to the application source repository.

In a new working directory:

```sh
curl -fLO https://github.com/socfortress/waf-platform-public/releases/download/v1.0.31/socfortress-php2shell-1.0.0.tar.gz
curl -fLO https://github.com/socfortress/waf-platform-public/releases/download/v1.0.31/socfortress-php2shell-1.0.0.tar.gz.sha256
sha256sum -c socfortress-php2shell-1.0.0.tar.gz.sha256
tar -xzf socfortress-php2shell-1.0.0.tar.gz
cd socfortress-php2shell-1.0.0
sha256sum -c SHA256SUMS
```

On macOS, use `shasum -a 256 -c` instead of `sha256sum -c`. Only extract after
the archive checksum passes. The public distribution updates documentation links
and reproduction instructions; the 1.0.0 rules, generator and HTTP fixtures are
unchanged. Its archive checksum therefore differs from the earlier distribution.
Use the checksum supplied alongside this public download.

## Generate a scoped copy

Requires Python 3.10+; no third-party dependencies. From this directory:

```sh
python3 render.py --host app.example.com --host www.example.com \
  --profile uploads --out /tmp/php2shell-app
```

Use `--profile strict` only if the selected hosts need no multipart forms.
Use `--max-body-bytes 16777216`, for example, only after reviewing application
requirements. Accepted budgets range from 1 KiB to 32 MiB; those are generator
bounds, not a claim that any particular PHP allocation is safe.

The output directory must not already exist. Each `.conf` is one Advanced Rules
entry with one `id:AUTO`. Its matching `.json` is a request body for the platform's
`POST /api/v1/rules/custom` API, if you prefer your existing authenticated API
workflow. `manifest.json` records the scope, profile, budget, and rule hashes.
Never submit `id:AUTO` directly to Coraza: the SOCFortress API replaces it.

The checked-in examples use `protected.example.invalid`; they intentionally do
not match your sites. **Generate your own copy instead of pasting them unchanged.**

## Install through SOCFortress

1. Patch PHP and verify that traffic cannot bypass the WAF and reach the origin
   directly. Inventory hostname aliases, existing WAF bypasses and rule exclusions.
2. Select the appropriate profile/engine from the compatibility table. Enable
   blocking for the selected sites, and enable **request body inspection** for
   the uploads profile. Detection/learning mode does not enforce deny rules.
3. Review the certificate-validation paths described below. Confirm they cannot
   route arbitrary requests into PHP, or close that gap outside this pack first.
4. Save your current custom-rule list and site settings. In **Rules → Custom
   Rules → Advanced**, create **one entry per generated `.conf` file**. Paste the
   whole file, starting with `SecRule`, and keep `id:AUTO`. Do not combine files
   into one entry: repeated AUTO IDs would become duplicate numeric IDs.
5. Record the allocated IDs and names beginning `PHP2Shell 1.0.0`. Each save
   reloads the WAF; the pack is not fully installed until every entry is enabled.
   The platform shares custom rules across sites; the generated hostname chains
   provide scope. Install each profile/scope only once.
6. Use the Rules Sandbox or an isolated staging copy to check ordinary forms,
   real uploads, API payloads, hostname aliases and the intended denies before
   enabling the pack for production traffic. The synthetic lab is reproducible
   through [VALIDATION.md](VALIDATION.md); do not run stress or exploit tests on
   production. Confirm deny events have the pack message/tag and intended rule ID.

For log-only evaluation, change the first chain rule's `deny,status:...` to
`pass` while retaining `log`. That is observation only; restore the generated
deny actions to enforce. Do not rebuild these chained rules through the
structured editor; use Advanced mode to preserve their conditions and scope.

Do not edit the generated Caddyfile or shared custom-rule file inside a running
container: the management API can overwrite those changes.

## Body limits and bypass prerequisites

The custom decoded-body rule makes its decision **after body buffering and
parsing**. It is not a hard frontend memory limit. Configure a suitable hard
decoded-body limit in a supported proxy/platform configuration as well. For a
manually managed Coraza configuration, the relevant directives are
`SecRequestBodyLimit`, `SecRequestBodyNoFilesLimit`, and
`SecRequestBodyLimitAction Reject`, with `SecRequestBodyAccess On`. These are
engine directives, **not separate Advanced Rule entries**. Apply through your
managed configuration workflow; this pack does not change them. Do not rely
solely on Content-Length. A smaller existing limit may reject before the pack.

SOCFortress currently disables the rule engine early for
`/.well-known/acme-challenge/` and `/.well-known/pki-validation/`. Custom rules
loaded later **cannot restore coverage**. Preserve legitimate certificate
validation, but ensure these routes serve only validation resources and do not
forward arbitrary requests to PHP. Merely disabling a visible seeded ACME
custom rule does not remove the renderer's separate early exceptions.

SOCFortress also supports an explicit full trusted-IP bypass using a method
exception with `methods=*`. Those requests skip the WAF handler entirely and
therefore skip this pack. Review trusted-IP exceptions as well as hostname scope.
Other `ctl:ruleEngine=Off`, rule-removal actions, allow rules and alternate
routes can also bypass inspection. The pack cannot override those decisions.

## Coverage limits

- These are heuristic input controls, not an exploit signature covering all
  memory-corruption, fatal-error or cross-request stale-state behavior.
- The uploads profile intentionally **does not block the upload-progress field**.
  No raw-body signature is shipped: `REQUEST_BODY` is not populated by Coraza's
  multipart processor. Switching the processor to RAW would lose normal parsed
  multipart inspection. A parsed-name match alone does not resolve PHP/Coraza
  parsing differences. Both default/custom progress-field controls pass the lab.
- Malformed-body protection depends on the engine setting error flags. The
  observed 3.7.0 truncation gap is retained in validation evidence, not hidden as
  a successful block. Other parser discrepancies may remain even on 3.8.1.
- Budgets are not a proof that PHP cannot exhaust memory. Names, part headers,
  files and application work may amplify memory differently. No per-part byte
  limit, PHP process-state inspection or worker correlation is implemented.
- TLS, compressed-body decoding across proxy layers, raw HTTP/2 framing, real
  upstream applications, exploit execution and a production false-positive rate
  are outside this validation. Only plaintext, known-length and chunked HTTP/1.1
  wire traffic to an isolated local responder is exercised by the pack's lab.

## Rollback

Disable or delete the entries identified by the recorded IDs and
`PHP2Shell 1.0.0` names. Since rules are independent, removal order is irrelevant.
Check the reload succeeded and rerun an ordinary application request. Revert any
separately changed proxy limits through their own configuration workflow.
Removing this pack does not reverse PHP updates and should not be used to do so.
For a false positive, scope or adjust the specific control after inspection;
do not disable the whole WAF or add a broad engine-off path.

## Sources and redistribution

Reviewed 22 October 2026. The nesting heuristic and mitigation research derive
from CrowdSec's [109618 rule](https://raw.githubusercontent.com/crowdsecurity/hub/master/appsec-rules/crowdsecurity/vpatch-CVE-2026-109618.yaml)
and [rationale](https://raw.githubusercontent.com/crowdsecurity/hub/master/appsec-rules/crowdsecurity/vpatch-CVE-2026-109618.md).
The header-budget design is a SOCFortress adaptation, not a verbatim equivalent
of their file counter. The raw-body limitation is documented in
[Coraza's variables reference](https://www.coraza.io/docs/seclang/variables/#request_body).
Also see the PHP [OOM advisory](https://github.com/php/php-src/security/advisories/GHSA-w8hw-w9fx-j79w)
and [stale-state advisory](https://github.com/php/php-src/security/advisories/GHSA-6wmf-4rv5-p3rp).

Redistribute with [LICENSE](LICENSE), including the CrowdSecurity attribution.
Describe this release as **partial request-pattern mitigation**, not a complete
virtual patch or a substitute for updating PHP. Publish the compatibility table,
coverage limits and validation evidence alongside the rules.
