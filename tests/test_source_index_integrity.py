"""Structural-integrity guard for the discovery index (7.5k rows).

``cannavec_science/data/primary_source_index.csv`` is the candidate pool for
live discovery and the ranker. Its rows are *not* curated facts (Constitution
§IX — they pass verify + GRADE before surfacing, and a human gate before
promotion), so they are not individually citation-audited. But the file is
still load-bearing: a malformed identifier, an identifier/URL mismatch, a
duplicate, or a lying ``curated`` flag would corrupt discovery and ranking.

This guard makes those invariants enforceable offline, on every change:

1. ``type`` is one of PubMed / PMC / DOI.
2. ``identifier`` is well-formed for its ``type``.
3. the identifier actually appears in its ``url`` (no copy-paste drift).
4. ``curated`` is a clean boolean.
5. identifiers are unique across the index.
6. every ``curated=true`` identifier is genuinely present in the registry
   source — i.e. the "already promoted" claim is true, not aspirational.

All offline; no network. Complements tests/test_source_index.py (API behaviour)
and the citation-integrity guard (curated-tier identifiers).
"""

from __future__ import annotations

import glob
import os
import re
import unittest

from cannavec_science.source_index import load_index

_PKG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cannavec_science",
)

_VALIDATORS = {
    "PubMed": re.compile(r"^\d{4,9}$"),
    "PMC": re.compile(r"^PMC\d+$"),
    "DOI": re.compile(r"^10\.\d{4,9}/\S+$"),
}


class DiscoveryIndexIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_index()

    def test_nonempty(self) -> None:
        self.assertGreater(len(self.rows), 1000, "discovery index looks truncated")

    def test_type_and_identifier_wellformed(self) -> None:
        bad = []
        for s in self.rows:
            validator = _VALIDATORS.get(s.type)
            if validator is None or not validator.match(s.identifier):
                bad.append((s.type, s.identifier))
        self.assertEqual(bad, [], f"{len(bad)} rows have a bad type/identifier: {bad[:5]}")

    def test_identifier_present_in_url(self) -> None:
        drift = [s.identifier for s in self.rows if s.identifier not in s.url]
        self.assertEqual(
            drift, [], f"{len(drift)} rows whose identifier is not in their url: {drift[:5]}"
        )

    def test_identifiers_unique(self) -> None:
        seen: dict[str, int] = {}
        for s in self.rows:
            seen[s.identifier] = seen.get(s.identifier, 0) + 1
        dups = {k: v for k, v in seen.items() if v > 1}
        self.assertEqual(dups, {}, f"{len(dups)} duplicate identifiers: {list(dups)[:5]}")

    def test_curated_flag_is_truthful(self) -> None:
        # Every row flagged as already-promoted must actually be cited somewhere
        # in the curated registry source. A curated=true row whose identifier is
        # absent from the package is a lying flag.
        src = "".join(
            open(p, encoding="utf-8").read()
            for p in glob.glob(os.path.join(_PKG, "*.py"))
        )
        liars = [s.identifier for s in self.rows if s.curated and s.identifier not in src]
        self.assertEqual(
            liars, [], f"{len(liars)} curated=true identifiers absent from registries: {liars[:5]}"
        )


if __name__ == "__main__":
    unittest.main()
