# tests/test_kb_audit_scope.py
import os
import tempfile
import unittest
from cannavec_science.kb_audit.scope import is_in_scope, select_files

_DEFAULT = ("cannabis/5. Medical & Therapeutic Use", "cannabis/6. Evidence & Clinical Validation")


class ScopeTests(unittest.TestCase):
    def test_medical_and_evidence_are_in_scope(self):
        self.assertTrue(is_in_scope("cannabis/5. Medical & Therapeutic Use/x.md", _DEFAULT, ()))
        self.assertTrue(is_in_scope("cannabis/6. Evidence & Clinical Validation/y.md", _DEFAULT, ()))

    def test_non_science_and_readme_out_of_scope(self):
        self.assertFalse(is_in_scope("cannabis-faq/conditions/x.md", _DEFAULT, ()))
        self.assertFalse(is_in_scope("cannabis/9. Regulation, Law & Compliance/x.md", _DEFAULT, ()))
        self.assertFalse(is_in_scope("cannabis/5. Medical & Therapeutic Use/README.md", _DEFAULT, ()))

    def test_exclude_overrides_include(self):
        self.assertFalse(is_in_scope("cannabis/5. Medical & Therapeutic Use/draft.md",
                                     _DEFAULT, ("draft",)))

    def test_select_files_skips_empty_and_nonmd(self, ):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "cannabis", "5. Medical & Therapeutic Use")
            os.makedirs(base)
            open(os.path.join(base, "full.md"), "w").write("# x\nbody\n")
            open(os.path.join(base, "empty.md"), "w").write("")
            open(os.path.join(base, "notes.txt"), "w").write("nope")
            got = select_files(d, _DEFAULT, ())
            self.assertEqual([os.path.basename(p) for p in got], ["full.md"])


if __name__ == "__main__":
    unittest.main()
