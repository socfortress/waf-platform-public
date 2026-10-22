#!/usr/bin/env python3
"""Build local-only Caddy configurations and inert HTTP test cases."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pack", ROOT / "render.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


def multipart(parts=1, depth=0, files=False, repeated=False, extra_headers=0):
    body = ""
    for i in range(parts):
        name = "field" + ("" if repeated else str(i)) + "[a]" * depth
        body += f'--bound\r\nContent-Disposition: form-data; name="{name}"'
        if files:
            body += '; filename=""'
        body += "\r\n"
        if files:
            body += "Content-Type: application/octet-stream\r\n"
        body += "".join(f"X-Part-{j}: inert\r\n" for j in range(extra_headers))
        body += "\r\n" + ("" if files else "ordinary") + "\r\n"
    return body + "--bound--\r\n"


def cases():
    out = []
    ct = "multipart/form-data; boundary=bound"

    def add(name, body, status=200, content_type=ct, **kwargs):
        out.append(dict(name=name, body=body, status=status, content_type=content_type, **kwargs))

    add("ordinary_form", multipart())
    add("ordinary_upload", multipart(files=True).replace('filename=""', 'filename="report.txt"'))
    for n in [11, 12, 13]:
        add(f"nesting_{n}", multipart(depth=n), 403 if n >= 12 else 200)
    for n in [49, 50, 51]:
        for repeated in [False, True]:
            add(f"empty_files_{n}_repeated_{repeated}", multipart(n, files=True, repeated=repeated), 403 if n > 50 else 200)
    for n in [99, 100, 101]:
        add(f"header_lines_{n}", multipart(extra_headers=n-1), 403 if n > 100 else 200)
    add("repeat_field_parts_101", multipart(101, repeated=True), 403)
    add("malformed_part", '--bound\r\nInvalid Header\r\n\r\nordinary\r\n--bound--\r\n', 400)
    add("truncated_multipart", multipart()[:-12], 400)
    add("progress_known_gap", multipart().replace("field0", "PHP_SESSION_UPLOAD_PROGRESS"))
    add("progress_custom_known_gap", multipart().replace("field0", "CUSTOM_PROGRESS"))
    add("json_control", '{"message":"ordinary"}', content_type="application/json")
    add("urlencoded_control", "message=ordinary", content_type="application/x-www-form-urlencoded")
    for n in [4095, 4096, 4097]:
        add(f"decoded_size_{n}", "value="+"a"*(n-6), 413 if n > 4096 else 200, content_type="application/x-www-form-urlencoded")
    add("duplicate_content_type", multipart(), 400, duplicate_type=True)
    add("mixed_case", multipart(depth=12), 403, content_type='Multipart/Form-Data ; boundary="bound"')
    add("unscoped_host", multipart(depth=12), host="other.test")
    add("host_suffix_not_scoped", multipart(depth=12), host="protected.test.evil.test")
    add("host_case_port", multipart(depth=12), 403, host="PROTECTED.TEST:8080")
    add("host_trailing_dot", multipart(depth=12), 403, host="protected.test.")
    add("extensionless", multipart(depth=12), 403, path="/upload")
    add("acme_known_gap", multipart(depth=12), path="/.well-known/acme-challenge/test")
    add("dcv_known_gap", multipart(depth=12), path="/.well-known/pki-validation/test")
    return out


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    configs = {}
    for offset, (profile, mode, body_access, partial, reverse) in enumerate([
        ("uploads", "On", True, False, False),
        ("strict", "On", True, False, False),
        ("uploads", "DetectionOnly", True, False, False),
        ("uploads", "On", False, False, False),
        ("uploads", "On", True, True, False),
        ("uploads", "On", True, False, True),
    ]):
        entries = pack.rules(["protected.test"], profile, 4096)
        if reverse:
            entries.reverse()
        text = "\n".join(rule.replace("id:AUTO", f"id:{9500000+i}") for i, (_, rule) in enumerate(entries))
        # Mirrors the platform's earlier exceptions and custom-rule insertion.
        directives = f'''SecRuleEngine {mode}
SecRequestBodyAccess {"On" if body_access else "Off"}
SecResponseBodyAccess Off
SecAuditEngine Off
SecRequestBodyLimit {2048 if partial else 131072}
SecRequestBodyNoFilesLimit {2048 if partial else 131072}
SecRequestBodyLimitAction {"ProcessPartial" if partial else "Reject"}
SecRule REQUEST_URI "@beginsWith /.well-known/acme-challenge/" "id:9001001,phase:1,pass,nolog,ctl:ruleEngine=Off"
SecRule REQUEST_URI "@beginsWith /.well-known/pki-validation/" "id:9001003,phase:1,pass,nolog,ctl:ruleEngine=Off"
{text}'''
        configs[str(8080+offset)] = {"listen": [f":{8080+offset}"], "routes": [{"handle": [
            {"handler": "waf", "directives": directives},
            {"handler": "static_response", "body": "upstream-reached", "status_code": 200}]}]}
        (out / f"directives-{8080+offset}.conf").write_text(directives)
    for pl in [1, 2]:
        server = json.loads(json.dumps(configs["8080"]))
        port = 8085 + pl
        server["listen"] = [f":{port}"]
        handler = server["routes"][0]["handle"][0]
        prefix, custom = handler["directives"].split('SecRule REQUEST_HEADERS:Host', 1)
        handler["directives"] = prefix + f'''Include /crs/crs-setup.conf
SecAction "id:9999001,phase:1,pass,nolog,setvar:tx.blocking_paranoia_level={pl},setvar:tx.detection_paranoia_level={pl}"
Include /crs/REQUEST-*.conf
Include /crs/RESPONSE-*.conf
SecRule REQUEST_HEADERS:Host{custom}'''
        configs[str(port)] = server
    (out / "caddy.json").write_text(json.dumps({"admin": {"disabled": True}, "apps": {"http": {"servers": configs}}}, indent=2))
    (out / "cases.json").write_text(json.dumps(cases(), indent=2))


if __name__ == "__main__":
    build(Path(sys.argv[1]))
