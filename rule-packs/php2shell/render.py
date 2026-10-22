#!/usr/bin/env python3
"""Render offline, hostname-scoped SOCFortress custom rules. Never installs them."""
import argparse
import hashlib
import json
import re
from pathlib import Path

VERSION = "1.0.0"


def host_pattern(hosts):
    normalized = sorted(set(h.lower().rstrip(".") for h in hosts))
    if not normalized:
        raise ValueError("at least one hostname is required")
    for host in normalized:
        if len(host) > 253 or not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*", host
        ):
            raise ValueError("use bare ASCII DNS names, without ports, wildcards or URLs")
    return r"(?i)^(?:" + "|".join(re.escape(h) for h in normalized) + r")\.?(?::[0-9]+)?$"


def rules(hosts, profile="uploads", max_body_bytes=8 * 1024 * 1024):
    if profile not in {"uploads", "strict"}:
        raise ValueError("unknown profile")
    if not 1024 <= max_body_bytes <= 32 * 1024 * 1024:
        raise ValueError("body limit must be 1024..33554432 bytes")
    scope = host_pattern(hosts)
    result = []

    def add(slug, phase, status, conditions):
        action = (f"id:AUTO,phase:{phase},t:none,deny,status:{status},log,"
                  f"msg:'SOCFortress PHP2Shell {slug}',tag:'socfortress/php2shell/1.0.0',chain")
        lines = [f'SecRule REQUEST_HEADERS:Host "@rx {scope}" "{action}"']
        for i, (target, operator, transforms) in enumerate(conditions):
            actions = transforms + (",chain" if i < len(conditions) - 1 else "")
            lines.append(f'SecRule {target} "{operator}" "{actions}"')
        result.append((slug, "\n".join(lines) + "\n"))

    multipart = ("REQUEST_HEADERS:Content-Type", r"@rx ^\s*multipart/form-data(?:\s*;|\s*$)", "t:none,t:lowercase")
    add("duplicate-content-type", 1, 400, [("&REQUEST_HEADERS:Content-Type", "@gt 1", "t:none")])
    add("incomplete-or-invalid-body", 2, 400, [
        ("REQBODY_ERROR|MULTIPART_STRICT_ERROR|INBOUND_DATA_ERROR", "!@eq 0", "t:none")])
    add("deep-multipart-name", 2, 403, [multipart,
        ("ARGS_POST_NAMES|FILES_NAMES", r"@rx (?:\[[^\]]*\]){12}", "t:none")])
    # Count all parsed part-header lines directly. Independent rules remain safe
    # if the platform changes DB row order; no counter/threshold ordering dependency.
    add("multipart-header-budget", 2, 403, [multipart,
        ("&MULTIPART_PART_HEADERS", "@gt 100", "t:none")])
    add("decoded-body-budget", 2, 413, [
        ("REQUEST_BODY_LENGTH", f"@gt {max_body_bytes}", "t:none")])
    if profile == "strict":
        add("multipart-disabled", 1, 403, [multipart])
    return result


def render(out, hosts, profile, max_body_bytes):
    entries = rules(hosts, profile, max_body_bytes)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"pack": "socfortress-php2shell", "version": VERSION,
                "profile": profile, "hosts": hosts, "max_body_bytes": max_body_bytes,
                "coverage": "partial request-pattern mitigation; not a PHP patch",
                "files": {}}
    for i, (slug, text) in enumerate(entries, 1):
        filename = f"{i:02d}-{slug}.conf"
        (out / filename).write_text(text)
        manifest["files"][filename] = hashlib.sha256(text.encode()).hexdigest()
        payload = {"name": f"PHP2Shell {VERSION}: {slug}",
                   "description": "Partial mitigation. See pack README and coverage limits.",
                   "raw_conf_text": text}
        (out / f"{i:02d}-{slug}.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append", required=True)
    parser.add_argument("--profile", choices=["uploads", "strict"], default="uploads")
    parser.add_argument("--max-body-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        render(args.out, args.host, args.profile, args.max_body_bytes)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
