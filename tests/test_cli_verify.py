"""CLI verify regression tests (spec 003 US5 / FR-005).

The verify surface must accept all five Constitution §I identifier
shapes (PMID, DOI, NCT, ChEMBL, UniProt). Pre-v0.3, only PMID and DOI
resolved; the other three returned ``[error] not a recognized
identifier``. These tests pin the new behaviour.
"""

from __future__ import annotations

import argparse
import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from cannavec_science.__main__ import (
    _classify_identifier,
    _cmd_verify,
)
from cannavec_science.pubmed_verify import (
    VerificationResult,
    VerificationVerdict,
)


# ── Identifier classification ─────────────────────────────────────────


class IdentifierClassifierTests(unittest.TestCase):

    def test_pmid_classified(self):
        self.assertEqual(_classify_identifier("28538134"), "PMID")

    def test_doi_classified(self):
        self.assertEqual(
            _classify_identifier("10.1056/NEJMoa1611618"), "DOI",
        )

    def test_nct_classified(self):
        self.assertEqual(_classify_identifier("NCT02224560"), "NCT")
        # Case-insensitive (rendering uppercases for display).
        self.assertEqual(_classify_identifier("nct02224560"), "NCT")

    def test_chembl_classified(self):
        self.assertEqual(_classify_identifier("CHEMBL5803"), "ChEMBL")
        # Case-insensitive prefix.
        self.assertEqual(_classify_identifier("chembl5803"), "ChEMBL")

    def test_uniprot_classified(self):
        self.assertEqual(_classify_identifier("P21554"), "UniProt")
        self.assertEqual(_classify_identifier("P34972"), "UniProt")
        self.assertEqual(_classify_identifier("Q8NER1"), "UniProt")

    def test_unknown_classified(self):
        self.assertEqual(_classify_identifier("XYZ123"), "unknown")
        self.assertEqual(_classify_identifier(""), "unknown")


# ── NCT verify ────────────────────────────────────────────────────────


_NCT_PAYLOAD = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT02224560"},
        "statusModule": {
            "overallStatus": "COMPLETED",
            "startDateStruct": {"date": "2014-04"},
        },
        "designModule": {
            "phases": ["PHASE3"],
            "enrollmentInfo": {"count": 120},
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "GW Pharmaceuticals"},
            "responsibleParty": {
                "investigatorFullName": "Orrin Devinsky, MD",
            },
        },
        "conditionsModule": {"conditions": ["Dravet Syndrome"]},
        "armsInterventionsModule": {
            "interventions": [
                {"name": "Cannabidiol"},
                {"name": "Placebo"},
            ],
        },
        "outcomesModule": {
            "primaryOutcomes": [
                {"measure": "Median percent change in convulsive seizure frequency"},
            ],
        },
        "contactsLocationsModule": {
            "locations": [
                {"country": "United States"},
                {"country": "United States"},
            ],
        },
    },
}


def _green_ctgov(_url: str) -> str:
    return json.dumps(_NCT_PAYLOAD)


def _not_found_ctgov(_url: str) -> str:
    raise urllib.error.HTTPError(
        url=_url, code=404, msg="Not Found", hdrs=None, fp=None,
    )


class NCTVerifyTests(unittest.TestCase):

    def test_nct_resolves_to_trial_record(self):
        args = argparse.Namespace(
            identifier="NCT02224560",
            json=False,
            no_citation_network=False,
        )
        with patch(
            "cannavec_science.ctgov_discover.default_ctgov_fetcher",
            new=_green_ctgov,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("NCT02224560", out)
        self.assertIn("Dravet Syndrome", out)
        self.assertIn("Cannabidiol", out)
        # Primary outcome surfaces.
        self.assertIn("convulsive seizure", out)
        self.assertIn("PASS", out)

    def test_nct_json_output(self):
        args = argparse.Namespace(
            identifier="NCT02224560", json=True, no_citation_network=False,
        )
        with patch(
            "cannavec_science.ctgov_discover.default_ctgov_fetcher",
            new=_green_ctgov,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["kind"], "NCT")
        self.assertEqual(payload["trial"]["nct_id"], "NCT02224560")


# ── ChEMBL verify ─────────────────────────────────────────────────────


_CHEMBL_PAYLOAD = {
    "molecule_chembl_id": "CHEMBL5803",
    "pref_name": "CANNABIDIOL",
    "molecule_type": "Small molecule",
    "molecule_properties": {
        "full_molformula": "C21H30O2",
        "full_mwt": 314.46,
    },
    "molecule_structures": {
        "canonical_smiles": "CCCCCc1cc(O)c2c(c1)OC(C)(C)[C@@H]1CCC(C)=C[C@H]21",
        "standard_inchi_key": "QHMBSVQNZZTUGM-ZWKOTPCHSA-N",
    },
}


def _green_chembl(_url: str) -> str:
    return json.dumps(_CHEMBL_PAYLOAD)


def _not_found_chembl(_url: str) -> str:
    raise urllib.error.HTTPError(
        url=_url, code=404, msg="Not Found", hdrs=None, fp=None,
    )


class ChEMBLVerifyTests(unittest.TestCase):

    def test_chembl_resolves_to_compound_record(self):
        args = argparse.Namespace(
            identifier="CHEMBL5803",
            json=False,
            no_citation_network=False,
        )
        with patch(
            "cannavec_science.chembl_discover.default_chembl_fetcher",
            new=_green_chembl,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("CHEMBL5803", out)
        self.assertIn("CANNABIDIOL", out)
        self.assertIn("C21H30O2", out)
        self.assertIn("PASS", out)

    def test_chembl_json_output(self):
        args = argparse.Namespace(
            identifier="CHEMBL5803", json=True, no_citation_network=False,
        )
        with patch(
            "cannavec_science.chembl_discover.default_chembl_fetcher",
            new=_green_chembl,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["kind"], "ChEMBL")
        self.assertEqual(payload["compound"]["chembl_id"], "CHEMBL5803")
        self.assertEqual(payload["compound"]["pref_name"], "CANNABIDIOL")


# ── UniProt verify ────────────────────────────────────────────────────


_UNIPROT_PAYLOAD = {
    "primaryAccession": "P21554",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Cannabinoid receptor 1"},
        },
    },
    "genes": [{"geneName": {"value": "CNR1"}}],
    "organism": {
        "scientificName": "Homo sapiens",
        "taxonId": 9606,
    },
    "sequence": {"length": 472},
}


def _green_uniprot(_url: str) -> str:
    return json.dumps(_UNIPROT_PAYLOAD)


class UniProtVerifyTests(unittest.TestCase):

    def test_uniprot_resolves_to_protein_record(self):
        args = argparse.Namespace(
            identifier="P21554", json=False, no_citation_network=False,
        )
        with patch(
            "cannavec_science.uniprot_verify.default_uniprot_fetcher",
            new=_green_uniprot,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("P21554", out)
        self.assertIn("Cannabinoid receptor 1", out)
        self.assertIn("CNR1", out)
        self.assertIn("Homo sapiens", out)
        self.assertIn("PASS", out)

    def test_uniprot_json_output(self):
        args = argparse.Namespace(
            identifier="P21554", json=True, no_citation_network=False,
        )
        with patch(
            "cannavec_science.uniprot_verify.default_uniprot_fetcher",
            new=_green_uniprot,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["kind"], "UniProt")
        self.assertEqual(payload["protein"]["accession"], "P21554")
        self.assertEqual(payload["protein"]["gene_symbol"], "CNR1")


# ── Unknown identifier error message lists all five shapes ────────────


class UnknownIdentifierTests(unittest.TestCase):
    def test_error_message_lists_all_five_shapes(self):
        args = argparse.Namespace(
            identifier="XYZ123", json=False, no_citation_network=False,
        )
        err = io.StringIO()
        with redirect_stderr(err):
            rc = _cmd_verify(args)
        self.assertEqual(rc, 2)
        msg = err.getvalue()
        # Spec US5 acceptance scenario 4 — every accepted shape is named.
        for shape in ("PMID", "DOI", "NCT", "ChEMBL", "UniProt"):
            self.assertIn(shape, msg)


# ── PMID verify verdict handling (fail-closed) ────────────────────────


def _mk_result(verdict, **kw):
    return VerificationResult(identifier="28538134", verdict=verdict, **kw)


class PMIDVerifyVerdictTests(unittest.TestCase):
    """The PMID verify path must branch on the typed verdict and fail
    CLOSED: a network/transport failure is UNVERIFIED (non-zero), never a
    PASS (Constitution §I — a citation is trustworthy only once the upstream
    record is confirmed). Regression for the fail-open where any truthy
    result rendered PASS and author/year always showed '?'.
    """

    def _run(self, result, *, json_mode=False):
        args = argparse.Namespace(
            identifier="28538134", json=json_mode, no_citation_network=True,
        )
        with patch(
            "cannavec_science.pubmed_verify.verify_pmid", return_value=result,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_verify(args)
        return rc, buf.getvalue()

    def test_match_renders_pass_with_author_and_year(self):
        rc, out = self._run(_mk_result(
            VerificationVerdict.MATCH,
            actual_first_author="Devinsky", actual_year=2017,
            journal="N Engl J Med", title="Trial of Cannabidiol...",
            retraction_status="clean",
        ))
        self.assertEqual(rc, 0)
        self.assertIn("PASS", out)
        # Field-name regression: author/year now render (were always '?').
        self.assertIn("Devinsky", out)
        self.assertIn("2017", out)

    def test_network_error_is_unverified_not_pass(self):
        rc, out = self._run(_mk_result(
            VerificationVerdict.NETWORK_ERROR,
            notes=("network error: HTTPError: HTTP Error 403: Forbidden",),
        ))
        self.assertNotEqual(rc, 0)            # fail closed
        self.assertIn("UNVERIFIED", out)
        self.assertNotIn("PASS", out)

    def test_not_found_is_fail_not_pass(self):
        rc, out = self._run(_mk_result(VerificationVerdict.NOT_FOUND))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)
        self.assertNotIn("PASS", out)

    def test_network_error_json_marks_unverified(self):
        rc, out = self._run(
            _mk_result(VerificationVerdict.NETWORK_ERROR, notes=("boom",)),
            json_mode=True,
        )
        self.assertNotEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["verdict"], "UNVERIFIED")
        self.assertNotIn("PASS", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
