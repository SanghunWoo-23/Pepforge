"""Regression tests for optimized V8 risk review."""
import unittest
from unittest.mock import patch
from suite_gui import v8_decision_support as support
from suite_gui.sequence_risk_map_v8 import build_sequence_risk_map


class TestOptimizedReview(unittest.TestCase):
    def test_cached_risk_matches_uncached(self):
        for sequence in ("Ac-EEMQRR-NH2", "GP-Hyp-GP-Hyp", "ACDEFGHIKLMNPQRSTVWY"):
            risk = build_sequence_risk_map(sequence)
            self.assertEqual(support.decision_report(sequence), support.decision_report_from_risk(risk))

    def test_cached_risk_does_not_reparse(self):
        risk = build_sequence_risk_map("Ac-EEMQRR-NH2")
        with patch.object(support, "build_sequence_risk_map", side_effect=AssertionError("Reanalysis")):
            result = support.decision_report_from_risk(risk)
        self.assertEqual(result["risk_map"], risk)
        self.assertFalse(result["chemistry_plan_modified"])

    def test_reject_invalid_cached_risk(self):
        for invalid in (None, {}, {"findings": None}):
            with self.assertRaises(ValueError):
                support.decision_report_from_risk(invalid)
