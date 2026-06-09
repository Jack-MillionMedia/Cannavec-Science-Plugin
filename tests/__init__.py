"""Cannavec test package.

Hermetic-cache fixture: the live-retrieval flywheel (``live_cache``) writes
through to a SQLite store on every discovery. Point that store at a throwaway
tmp dir for the whole offline suite so no test ever writes to the package
``data/`` directory or leaks cached rows across runs. Production (where this
package is never imported) keeps the durable default. An explicit
``CANNAVEC_CACHE_DIR`` — set by a test via ``patch.dict`` — still wins.
"""

import atexit
import os
import shutil
import tempfile

if not os.environ.get("CANNAVEC_CACHE_DIR"):
    _CACHE_TMP = tempfile.mkdtemp(prefix="cannavec-test-cache-")
    os.environ["CANNAVEC_CACHE_DIR"] = _CACHE_TMP
    atexit.register(lambda: shutil.rmtree(_CACHE_TMP, ignore_errors=True))
