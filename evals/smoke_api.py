#!/usr/bin/env python3
"""Live API smoke + contract tester for a deployed Cannavec Science instance.

Probes a running deployment (Vercel or any host) and asserts not just *liveness*
but the **constitution invariants** the engine promises — every answer is cited
(§I), the THCA-vs-THC detector fires (§VI), curated registries are present, and
the error paths return the right status codes. Exits non-zero on any failure, so
it gates a post-deploy CI job or a manual check.

Stdlib only (``urllib``) — no dependencies, runs anywhere Python ≥ 3.9 does.

Usage
-----
    python3 evals/smoke_api.py https://your-app.vercel.app
    CANNAVEC_API_BASE=https://your-app.vercel.app python3 evals/smoke_api.py
    python3 evals/smoke_api.py https://your-app.vercel.app --live   # also probe /api/discover

Vercel Deployment Protection
----------------------------
If the deployment is gated (a 401/403 before your code runs), create a
"Protection Bypass for Automation" secret in the Vercel project settings and
export it — the requests will carry the bypass header automatically::

    export VERCEL_AUTOMATION_BYPASS_SECRET=xxxxxxxx
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# The Devinsky 2017 NEJM CBD/Dravet RCT — pinned curated fact (also the CLI
# acceptance gate). Its presence proves the curated path is wired end to end.
_DRAVET_PMID = "28538134"
_MIN_REGISTRIES = 21


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


def _request(base: str, path: str, *, method: str = "GET",
             body: dict | None = None, token: str | None = None,
             timeout: int = 25) -> tuple[int, dict, bytes]:
    """One HTTP round-trip. Returns ``(status, headers_lower, body_bytes)``.

    Non-2xx responses are captured (not raised) so error-path assertions can
    inspect the status + body. A Vercel protection-bypass token, when given, is
    sent as the ``x-vercel-protection-bypass`` header.
    """
    url = base.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["x-vercel-protection-bypass"] = token
        headers["x-vercel-set-bypass-cookie"] = "true"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read()


def _json(raw: bytes):
    try:
        return json.loads(raw or b"{}")
    except (ValueError, TypeError):
        return None


def run_checks(base: str, *, token: str | None = None, live: bool = False,
               timeout: int = 25) -> list[Result]:
    """Run the full invariant suite against ``base``; return one Result each."""
    out: list[Result] = []

    def check(name: str, fn) -> None:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 — a transport error is a failure
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        out.append(Result(name, ok, detail))

    # 1. health — liveness + curated registry count + capability surface.
    def health():
        st, _, raw = _request(base, "/api/health", token=token, timeout=timeout)
        p = _json(raw)
        if st in (401, 403):
            return False, (f"HTTP {st} — deployment gated before the handler "
                           f"(Vercel Deployment Protection?). Set "
                           f"VERCEL_AUTOMATION_BYPASS_SECRET. body={raw[:80]!r}")
        if st != 200 or not p:
            return False, f"HTTP {st}, body={raw[:120]!r}"
        if p.get("status") != "ok":
            return False, f"status={p.get('status')} error={p.get('error')}"
        n = p.get("curated_registries", 0)
        if n < _MIN_REGISTRIES:
            return False, f"curated_registries={n} (< {_MIN_REGISTRIES})"
        return True, f"v{p.get('version')} phase={p.get('phase')} registries={n}"
    check("health 200 + registries", health)

    # 2. registries — inventory is valid JSON.
    def registries():
        st, _, raw = _request(base, "/api/registries", token=token, timeout=timeout)
        p = _json(raw)
        if st != 200 or p is None:
            return False, f"HTTP {st}, parseable={p is not None}"
        return True, "inventory JSON ok"
    check("registries 200 + JSON", registries)

    # 3. rigor — the THCA-vs-THC detector MUST fire (§VI deterministic).
    def rigor():
        q = urllib.parse.urlencode({"text": "this cultivar tests at 22% THC by HPLC"})
        st, _, raw = _request(base, f"/api/rigor?{q}", token=token, timeout=timeout)
        p = _json(raw) or {}
        if st != 200:
            return False, f"HTTP {st}"
        if p.get("clean") is not False:
            return False, f"expected clean=false, got {p.get('clean')}"
        n = (p.get("counts") or {}).get("thca_thc_violations", 0)
        if n < 1:
            return False, f"thca_thc_violations={n} (expected ≥1)"
        return True, f"thca_thc_violations={n}"
    check("rigor flags THCA/THC (§VI)", rigor)

    # 4. rigor error path — missing text → 400.
    def rigor_400():
        st, _, raw = _request(base, "/api/rigor", method="POST", body={},
                              token=token, timeout=timeout)
        return (st == 400, f"HTTP {st} (expected 400)")
    check("rigor missing text → 400", rigor_400)

    # 5. answer — curated brief is cited (§I) and graded (§VII).
    def answer():
        q = urllib.parse.urlencode({"question": "CBD evidence in Dravet syndrome"})
        st, _, raw = _request(base, f"/api/answer?{q}", token=token, timeout=timeout)
        p = _json(raw) or {}
        if st != 200 or not p.get("ok"):
            return False, f"HTTP {st}, ok={p.get('ok')}"
        ans = p.get("answer") or {}
        claims = ans.get("claims") or []
        cites = ans.get("citations") or []
        pmids = {c.get("pmid") for c in cites if c.get("pmid")}
        if not claims:
            return False, "0 claims (§I: curated answer must be sourced)"
        if not pmids:
            return False, "0 cited PMIDs (§I)"
        if _DRAVET_PMID not in pmids:
            return False, f"Devinsky {_DRAVET_PMID} absent — got {sorted(pmids)[:4]}"
        if p.get("augmented") not in (0, None) or p.get("fallback_used"):
            return False, "curated question unexpectedly fell back to live"
        return True, f"{len(claims)} claims, {len(pmids)} PMIDs incl. {_DRAVET_PMID}"
    check("answer cited + graded (§I/§VII)", answer)

    # 6. answer error path — missing question → 400.
    def answer_400():
        st, _, raw = _request(base, "/api/answer", token=token, timeout=timeout)
        p = _json(raw) or {}
        return (st == 400 and p.get("ok") is False, f"HTTP {st}, ok={p.get('ok')}")
    check("answer missing question → 400", answer_400)

    # 7. answer markdown — the citable brief renders.
    def answer_md():
        q = urllib.parse.urlencode({"question": "CBD evidence in Dravet syndrome",
                                    "format": "markdown"})
        st, hdrs, raw = _request(base, f"/api/answer?{q}", token=token, timeout=timeout)
        ok = st == 200 and (b"## " in raw or "markdown" in hdrs.get("content-type", ""))
        return (ok, f"HTTP {st}, content-type={hdrs.get('content-type')}")
    check("answer ?format=markdown", answer_md)

    # 8. (opt-in) discover — live fan-out returns a synthesis verdict. Needs the
    # deployment to have live discovery configured (NCBI key); off by default.
    if live:
        def discover():
            q = urllib.parse.urlencode({"query": "cannabidiol Dravet syndrome", "max": "3"})
            st, _, raw = _request(base, f"/api/discover?{q}", token=token, timeout=timeout)
            p = _json(raw) or {}
            if st != 200 or not p.get("ok"):
                return False, f"HTTP {st}, ok={p.get('ok')}"
            if "synthesis" not in p and "synthesis" not in (p.get("answer") or {}):
                return False, "no synthesis verdict in response"
            return True, "live fan-out + synthesis ok"
        check("discover live + synthesis", discover)

    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live API smoke + contract tester.")
    ap.add_argument("base", nargs="?", default=os.environ.get("CANNAVEC_API_BASE"),
                    help="Deployment base URL (or set CANNAVEC_API_BASE).")
    ap.add_argument("--live", action="store_true",
                    help="Also probe /api/discover (needs live discovery configured).")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    if not args.base:
        print("[smoke] no base URL — pass one or set CANNAVEC_API_BASE", file=sys.stderr)
        return 2

    token = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET")
    print(f"[smoke] {args.base}"
          + ("  (+bypass token)" if token else "")
          + ("  (+live)" if args.live else ""))
    results = run_checks(args.base, token=token, live=args.live, timeout=args.timeout)

    failed = 0
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        if not r.ok:
            failed += 1
        print(f"  [{mark}] {r.name:<34} {r.detail}")
    print(f"\n  {len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
