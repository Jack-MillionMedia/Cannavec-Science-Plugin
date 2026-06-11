"""The verified-source cache must be BOUNDED — a long-lived operator store
cannot grow without limit (the audit flagged record_discovery as having no
cap/TTL). Eviction keeps the freshest, most-hit rows and drops the oldest, and
removes their orphaned query_hits with them.

Stdlib only, offline, deterministic (timestamps injected via ``now``).
"""

from __future__ import annotations

import tempfile
import unittest

from cannavec_science import live_cache as lc

_NEVER_RETRACTED = lambda **_k: None  # noqa: E731 — tiny offline stub


class CacheIsBounded(unittest.TestCase):
    def _record(self, d, i, cap):
        payload = {"pubmed": [{"pmid": f"3000000{i}", "title": f"t{i}", "year": "2021"}]}
        lc.record_discovery(
            f"query number {i}", payload,
            store_dir=d, is_retracted=_NEVER_RETRACTED, max_sources=cap,
            now=f"2021-02-{i + 1:02d}T00:00:00+00:00",
        )

    def test_cache_respects_the_cap_and_evicts_oldest(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(10):  # 10 distinct sources, cap of 4
                self._record(d, i, cap=4)

            self.assertLessEqual(
                lc.stats(store_dir=d)["sources"], 4,
                "verified_sources grew past the cap — no eviction happened",
            )
            # Freshest (i=9) retained; oldest (i=0) evicted.
            fresh = lc.fetch_for_query(
                "query number 9", store_dir=d, is_retracted=_NEVER_RETRACTED
            )
            self.assertTrue(
                any(r.get("pmid") == "30000009" for r in fresh),
                "freshest source was wrongly evicted",
            )
            old = lc.fetch_for_query(
                "query number 0", store_dir=d, is_retracted=_NEVER_RETRACTED
            )
            self.assertEqual(old, [], "oldest source should have been evicted")

    def test_under_cap_keeps_everything(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                self._record(d, i, cap=100)
            self.assertEqual(lc.stats(store_dir=d)["sources"], 3)


if __name__ == "__main__":
    unittest.main()
