"""CLI tested as users actually invoke it — `python3 -m cannavec_science ...`.

The other `test_cli_*` suites call ``main(argv)`` in-process; this one spawns a
real subprocess so the module entry point, argument parsing, stdout/stderr
streams, and **process exit codes** are covered end to end. Every command here
is offline (no network), so it runs in the default suite. Exit-code contract:
0 = ok, 1 = refusal / violation, 2 = bad input / unknown command.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _cli(*args: str, timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cannavec_science", *args],
        cwd=str(_ROOT), capture_output=True, text=True, timeout=timeout,
    )


class CliSubprocessTest(unittest.TestCase):
    def test_no_args_prints_help_exit_0(self) -> None:
        p = _cli()
        self.assertEqual(p.returncode, 0)
        self.assertIn("usage", (p.stdout + p.stderr).lower())

    def test_unknown_subcommand_exit_2(self) -> None:
        p = _cli("definitely-not-a-command")
        self.assertEqual(p.returncode, 2)

    def test_rigor_violation_exits_1(self) -> None:
        # §VI THCA-vs-THC conflation → deterministic violation → exit 1.
        p = _cli("rigor", "this cultivar tests at 22% THC by HPLC")
        self.assertEqual(p.returncode, 1)
        self.assertIn("THCA", p.stdout + p.stderr)

    def test_rigor_clean_exits_0(self) -> None:
        p = _cli("rigor", "Cannabidiol is a phytocannabinoid studied in epilepsy.")
        self.assertEqual(p.returncode, 0)

    def test_answer_json_is_valid_and_cited(self) -> None:
        p = _cli("answer", "CBD evidence in Dravet syndrome", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        payload = json.loads(p.stdout)
        self.assertTrue(payload.get("claims"))
        pmids = {c.get("pmid") for c in payload.get("citations", [])}
        self.assertIn("28538134", pmids)  # Devinsky 2017 (§I)

    def test_answer_verified_flag_runs(self) -> None:
        # --verified weaves the (currently empty) verified tier; must not error.
        p = _cli("answer", "CBD evidence in Dravet syndrome", "--verified")
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_registries_exit_0(self) -> None:
        self.assertEqual(_cli("registries").returncode, 0)

    def test_curate_stats_exit_0(self) -> None:
        p = _cli("curate-stats")
        self.assertEqual(p.returncode, 0)
        self.assertIn("verified tier", p.stdout)

    def test_curate_sweep_dry_preview_exit_0(self) -> None:
        # Reads the committed demand log; dry preview (no --network) stages nothing.
        self.assertEqual(_cli("curate-sweep", "--holes", "3").returncode, 0)

    def test_verify_bad_identifier_exit_2(self) -> None:
        # Unrecognised identifier shape errors before any network call.
        p = _cli("verify", "not-an-identifier")
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
