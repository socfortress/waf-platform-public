# Validation record — 22 October 2026

Pack version: **1.0.0**, distributed separately from the Coraza upgrade.
No production configuration was modified. All isolated test servers were stopped.
No PHP origin or exploit was run.

| Target | Actual engine / connector | Result |
| --- | --- | --- |
| Cached `ghcr.io/socfortress/waf-caddy:1.0.26` | Coraza 3.7.0, coraza-caddy 2.5.0, `waf` | 228/228 expected outcomes, **including documented gaps**. Uploads profile has a truncated-body gap and is not recommended on this build. |
| `ghcr.io/socfortress/waf-caddy:1.0.30` | Coraza 3.8.1, coraza-caddy 2.6.2, Caddy 2.11.4, `waf` | **228/228 expected outcomes**, including documented gaps. Both profiles passed; the truncated multipart fixture returns 400. Linux/amd64 image, tested under emulation. |
| Python generator / platform editor contract | Standard-library unittest; platform 1.0.30 source | Six tests passed, including eleven generated Advanced Rule entries across the two profiles. |

The 3.7.0 release image allows the truncated multipart fixture in four cases
(two framing modes, normal/reversed rule order). This is an **engine limitation**,
not successful mitigation. Those allows remain explicitly marked as `known_gap`.
Other expected allows include certificate-path engine-off exceptions, progress
fields under the uploads profile, and body-based controls when inspection or
enforcement is disabled. Passing means behavior matches the specification;
it does not establish complete PHP2Shell protection.

## Evidence

- [Coraza 3.7.0 results](validation/coraza-3.7.0.json)
- [SOCFortress 1.0.30 results](validation/socfortress-1.0.30.json) and [binary build information](validation/socfortress-1.0.30-build-info.txt)
- [Image, configuration, corpus and CRS identities](validation/identity.json)

The older image digest is a locally cached identity, not a claim about a mutable
registry tag. The 1.0.30 registry image was pulled and verified by immutable digest after all
three release image jobs succeeded:
`sha256:72a3dae5d1290ea2a5354298c49752f88052d0de04780bd1efae33afb03e1fca`.
Its test corpus, lab configuration and managed CRS hashes match the earlier
3.7.0 comparison. The two image runs total 456 expected HTTP outcomes.

## What ran

Each image ran eight isolated local HTTP configurations:

| Internal port | Configuration |
| --- | --- |
| 8080 | Uploads profile, normal enforcement |
| 8081 | Strict profile |
| 8082 | DetectionOnly — expected enforcement gap |
| 8083 | Body inspection off — expected body-rule gap |
| 8084 | ProcessPartial, 2 KiB engine cap — pack rejects the incomplete-body flag |
| 8085 | Uploads rules in reverse order — no counter dependencies |
| 8086 | Uploads with full repository CRS 4.7.0 PL1 |
| 8087 | Uploads with full repository CRS 4.7.0 PL2 |

The full corpus exercises the isolated pack without CRS so existing generic
rules cannot hide a failing pack rule. The two full-CRS configurations provide
integration smoke coverage for a benign form, nested names and a body-budget
deny; they are not full production-profile certification.

Cases cover 11/12/13 bracket components, 49/50/51 empty files with distinct and
repeated field names, 99/100/101 part-header lines, 101 repeated ordinary field
parts, malformed/truncated multipart, controls with progress fields, benign
JSON/form/upload requests, hostname scope and suffix mismatches, case/port/dot
handling, mixed-case media type, extensionless routes, duplicate Content-Type,
and certificate-path bypasses. Every selected case runs with Content-Length and
with a real chunked HTTP/1.1 body split into 97-byte chunks. Allowed responses
must contain the synthetic responder's marker; rejected responses must not.

The pack's body-budget test uses **4,096 bytes** to keep the lab cheap, with
4,095/4,096/4,097 boundaries. It tests the generated operator with a scaled
threshold, not 8 MiB performance. The generator test separately checks that the
default rule renders 8,388,608. The native lab hard cap is 128 KiB except for the
explicit ProcessPartial scenario. The pack does not override these engine caps.

## Reproduce

### Engine upgrade

Install [SOCFortress 1.0.30](https://github.com/socfortress/waf-platform-public/releases/tag/v1.0.30)
first. It pins Coraza **3.8.1**, coraza-caddy **2.6.2** and Caddy **2.11.4**.
Coraza 3.8.1 is a security release recommending upgrades from 3.7.x; the
connector requires Caddy 2.11.4. Verify the deployed binary with
`docker compose exec caddy-waf caddy build-info` before applying the rules.
Sources: [engine release](https://github.com/corazawaf/coraza/releases/tag/v3.8.1),
[connector release](https://github.com/corazawaf/coraza-caddy/releases/tag/v2.6.2).

### Regression suite

Unit tests work in the unpacked publication directory:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The platform-editor test is skipped in the public repository and standalone
archive because the backend source is not included. The five generator tests
run without it. The six-test result above records the original release validation.

Full HTTP reproduction needs Docker, the public WAF and admin API images, and
a Python image. Obtain the exact seed CRS from the **public admin API image**;
no private checkout is needed. From this pack directory, choose unused temporary
paths/container names. The extraction container is created but never started:

```sh
docker pull --platform linux/amd64 ghcr.io/socfortress/waf-admin-api:1.0.30
mkdir /tmp/php2shell-crs
docker create --platform linux/amd64 --name php2shell-crs-source ghcr.io/socfortress/waf-admin-api:1.0.30
docker cp php2shell-crs-source:/etc/coraza/crs-bundle/. /tmp/php2shell-crs/
docker rm php2shell-crs-source
python3 - <<'CHECK_CRS'
import hashlib
import json
from pathlib import Path
identity = json.loads(Path('validation/identity.json').read_text())
root = Path('/tmp/php2shell-crs')
for name, expected in identity['crs_file_sha256'].items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f'CRS checksum mismatch: {name}')
print('All recorded CRS checksums verified')
CHECK_CRS
```

Then generate and start the isolated lab, still from this pack directory:

```sh
python3 tests/make_lab.py /tmp/php2shell-lab
docker run --rm --platform linux/amd64 --name php2shell-pack-lab --network none \
  --cpus 2 --memory 512m --read-only \
  --tmpfs /tmp:rw,size=64m --tmpfs /config:rw,size=16m --tmpfs /data:rw,size=16m \
  -v /tmp/php2shell-lab:/lab:ro \
  -v /tmp/php2shell-crs:/crs:ro \
  --entrypoint caddy ghcr.io/socfortress/waf-caddy:1.0.30 \
  run --config /lab/caddy.json
```

Keep that foreground process open. In another shell:

```sh
docker run --rm --network container:php2shell-pack-lab \
  -v "$PWD:/workspace:ro" -v /tmp/php2shell-lab:/lab:ro \
  python:3.12-slim python /workspace/tests/check_http.py \
  /lab --engine 3.8.1 > /tmp/php2shell-results.json
docker stop php2shell-pack-lab
```

For the historical 3.7.0 comparison, use the recorded 1.0.26 image and
`--engine 3.7.0`. The engine argument selects the documented truncation behavior;
verify it against `caddy build-info` instead of using it to conceal failures.
Never point these tests at a production origin: the client intentionally accepts
no remote-host argument.

Containers have no external network or published ports; the Python client shares
only the server's private network namespace. Tests use the actual Caddy binary
and connector, with a static synthetic responder in place of a PHP application.

## Build and verify the publication archive

From the pack directory:

```sh
python3 package.py
```

This creates `dist/socfortress-php2shell-1.0.0.tar.gz`, a companion archive SHA-256
file, and the included per-file `SHA256SUMS`. Verify the companion digest before
extracting, and `SHA256SUMS` after extracting, using your SHA-256 utility.
The archive includes the rule generator and the exact example rules, evidence,
license, installation/rollback instructions and tests; it includes no API token,
deployment configuration or automatic installer.

## Public distribution verification

The public copy retains the original 1.0.0 rule generator, example rules, HTTP
fixtures and validation records without changes. Documentation now uses public
release links and extracts the CRS from a public image for reproduction. The
archive and per-file checksums are regenerated for those documentation changes;
this does not represent another engine test run or different mitigation behavior.
