"""Guard: no module emits a SyntaxWarning (invalid escape sequence) at compile.

Python 3.12+ raises a ``SyntaxWarning`` for stray escapes like ``\\``` in a
regular string/docstring; it prints to stderr on every import and looks
unprofessional to an end user. This test fails the build if any module
reintroduces one (use a raw string ``r"..."`` for literal backslashes).
"""
from __future__ import annotations

import pathlib
import unittest
import warnings

_PKG = pathlib.Path(__file__).resolve().parent.parent / "cannavec_science"


class NoSyntaxWarningsTest(unittest.TestCase):
    def test_package_compiles_without_syntax_warnings(self):
        offenders: list[str] = []
        for path in sorted(_PKG.rglob("*.py")):
            src = path.read_text(encoding="utf-8")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    compile(src, str(path), "exec")
                except SyntaxError as exc:  # a hard error is also a failure
                    offenders.append(f"{path.name}: {exc}")
            for w in caught:
                if issubclass(w.category, SyntaxWarning):
                    offenders.append(f"{path.name}: {w.message}")
        self.assertEqual(offenders, [], "SyntaxWarnings found: " + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
