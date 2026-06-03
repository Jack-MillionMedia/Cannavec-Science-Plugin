"""API smoke/contract tests — offline against the local router, opt-in remote.

``LocalSmokeTest`` runs the full invariant harness (``evals/smoke_api.run_checks``)
against the bundled single-port router (``evals/serve_local``) on an ephemeral
localhost port. This is hermetic and offline — it exercises every endpoint and
every constitution-invariant assertion the live tester uses, so the harness
itself is covered by CI.

``RemoteSmokeTest`` runs the same harness against a real deployment, but only
when ``CANNAVEC_API_BASE`` is set (else skipped) — so a release pipeline can
point it at staging/prod without the default offline suite ever hitting the wire.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

_EVALS = Path(__file__).resolve().parent.parent / "evals"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _EVALS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses introspection (cls.__module__) resolves.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


smoke = _load("smoke_api")
serve_local = _load("serve_local")


class LocalSmokeTest(unittest.TestCase):
    """The harness + every endpoint, offline, on a localhost port."""

    def setUp(self) -> None:
        self.httpd = HTTPServer(("127.0.0.1", 0), serve_local.make_router())
        self.port = self.httpd.server_address[1]
        self._t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._t.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_all_invariants_pass(self) -> None:
        results = smoke.run_checks(self.base, live=False, timeout=20)
        failed = [r for r in results if not r.ok]
        self.assertEqual(
            failed, [],
            "smoke failures:\n" + "\n".join(f"  {r.name}: {r.detail}" for r in failed),
        )
        # Sanity: the harness actually ran the full set, not an empty pass.
        self.assertGreaterEqual(len(results), 7)


@unittest.skipUnless(
    os.environ.get("CANNAVEC_API_BASE"),
    "set CANNAVEC_API_BASE=https://... to run the remote-deployment smoke test",
)
class RemoteSmokeTest(unittest.TestCase):
    """Opt-in: the same harness against a live deployment."""

    def test_remote_invariants_pass(self) -> None:
        base = os.environ["CANNAVEC_API_BASE"]
        token = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET")
        live = os.environ.get("CANNAVEC_SMOKE_LIVE") == "1"
        results = smoke.run_checks(base, token=token, live=live, timeout=25)
        failed = [r for r in results if not r.ok]
        self.assertEqual(
            failed, [],
            f"remote smoke failures against {base}:\n"
            + "\n".join(f"  {r.name}: {r.detail}" for r in failed),
        )


if __name__ == "__main__":
    unittest.main()
