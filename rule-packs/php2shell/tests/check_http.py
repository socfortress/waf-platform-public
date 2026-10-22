#!/usr/bin/env python3
"""Bounded inert HTTP tests. Hardcoded loopback; no remote-target option."""
import argparse
import http.client
import json
import time
from pathlib import Path


def request(port, case, chunked=False):
    body = case["body"].encode()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest("POST", case.get("path", "/index.php"), skip_host=True)
        conn.putheader("Host", case.get("host", "protected.test"))
        conn.putheader("User-Agent", "SOCFortress-inert-regression")
        conn.putheader("Accept", "*/*")
        conn.putheader("Content-Type", case["content_type"])
        if case.get("duplicate_type"):
            conn.putheader("Content-Type", "application/json")
        if chunked:
            conn.putheader("Transfer-Encoding", "chunked")
            conn.endheaders()
            for i in range(0, len(body), 97):
                chunk = body[i:i+97]
                conn.send(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            conn.send(b"0\r\n\r\n")
        else:
            conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
        response = conn.getresponse()
        return response.status, response.read().decode(errors="replace")
    finally:
        conn.close()


def run(lab, engine):
    cases = json.loads((lab / "cases.json").read_text())
    for _ in range(50):
        try:
            request(8080, cases[0])
            break
        except OSError:
            time.sleep(.1)
    results = []
    for port in [8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087]:
        selected = cases if port in [8080, 8081, 8085] else [c for c in cases if c["name"] in ["ordinary_form", "nesting_12", "decoded_size_4097"]]
        for case in selected:
            expected = case["status"]
            scoped = case.get("host", "protected.test").lower() in ["protected.test", "protected.test.", "protected.test:8080"]
            bypass = case.get("path", "").startswith("/.well-known/")
            if port == 8081 and scoped and not bypass and case["content_type"].lower().startswith("multipart/"):
                expected = 403  # strict phase 1 runs before body processing
                if case.get("duplicate_type"):
                    expected = 400
            if port in [8082, 8083]:
                expected = 200
            if port == 8084 and len(case["body"].encode()) >= 2048:
                expected = 400  # incomplete body flag rejects ProcessPartial
            known_gap = None
            if engine == "3.7.0" and case["name"] == "truncated_multipart" and port in [8080, 8085]:
                expected = 200
                known_gap = "Coraza 3.7.0 fails to flag this truncated multipart body; uploads profile not recommended"
            if "known_gap" in case["name"] and expected == 200:
                known_gap = "documented uncovered input or engine-off path"
            if port in [8082, 8083] and case["status"] != 200:
                known_gap = "inspection or enforcement disabled"
            for chunked in [False, True]:
                try:
                    status, body = request(port, case, chunked)
                    passed = status == expected and ((body == "upstream-reached") == (expected == 200))
                    result = {"port": port, "case": case["name"], "chunked": chunked,
                              "expected": expected, "actual": status, "pass": passed}
                    if known_gap:
                        result["known_gap"] = known_gap
                except Exception as exc:
                    result = {"port": port, "case": case["name"], "chunked": chunked, "pass": False, "error": str(exc)}
                results.append(result)
    report = {"engine": engine, "complete_php2shell_protection": False,
              "test_body_budget": 4096,
              "cases": len(results), "passed": sum(r["pass"] for r in results), "results": results}
    print(json.dumps(report, indent=2))
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab", type=Path)
    parser.add_argument("--engine", choices=["3.7.0", "3.8.1"], required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.lab, args.engine))
