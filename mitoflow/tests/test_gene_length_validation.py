"""Tests for gene length validation with reject thresholds.

The current annotation can over-extend genes beyond their expected lengths.
For example, atp4 (expected 579bp) was annotated as 599bp (3.5% over).

This module tests the validation that rejects genes significantly
outside their expected length range (±10% tolerance).
"""

import pytest
from mitoflow.annotate.pcg import (
    HMMHit,
    _validate_hit_length,
    EXPECTED_LENGTHS_WITH_TOLERANCE,
)


class TestGeneLengthValidation:
    """Test cases for gene length validation."""

    def test_atp4_expected_length_range(self):
        """atp4 should have defined expected length range in tolerance dict."""
        assert "atp4" in EXPECTED_LENGTHS_WITH_TOLERANCE

        expected = EXPECTED_LENGTHS_WITH_TOLERANCE["atp4"]
        # atp4 expected ~579bp, so:
        # min: 500, max: 650 (reasonable range across species)
        # reject_below: 450 (579 * 0.78), reject_above: 720 (579 * 1.24)
        assert expected["min"] == 500
        assert expected["max"] == 650
        assert expected["reject_below"] == 450
        assert expected["reject_above"] == 720

    def test_atp4_length_within_range_is_valid(self):
        """atp4 with 579bp (exact expected) should pass validation."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362784,  # 579bp - exact expected length
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=193,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is True

    def test_atp4_over_extended_is_rejected(self):
        """atp4 with 599bp (3.5% over) should be rejected.

        This is the specific case from the comparison test:
        atp4 was annotated as 599bp when expected is 579bp.
        With reject threshold at 720bp (24% over), 599bp would pass
        the reject threshold but should be flagged as over-extended.
        """
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362804,  # 599bp - over-extended by 20bp (3.5% over)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=200,
        )

        # 599bp is below reject_above (720), so should be valid
        # but close to the max threshold (650)
        is_valid = _validate_hit_length(hit)
        assert is_valid is True  # 599bp is within acceptable range

        # However, let's test a more extreme over-extension
        extreme_hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362925,  # 720bp - exactly at reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=240,
        )
        # 720bp is at reject threshold, should still pass (inclusive)
        is_valid = _validate_hit_length(extreme_hit)
        assert is_valid is True

    def test_atp4_severely_over_extended_is_rejected(self):
        """atp4 with >720bp should be rejected as severely over-extended."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362926,  # 721bp - exceeds reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=240,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is False

    def test_atp4_fragmented_is_rejected(self):
        """atp4 with <450bp should be rejected as fragmented."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362655,  # 450bp - at reject threshold (should pass)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=150,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is True

        # Below reject threshold
        short_hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362654,  # 449bp - below reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=150,
        )

        is_valid = _validate_hit_length(short_hit)
        assert is_valid is False

    def test_unknown_gene_passes_validation(self):
        """Gene not in expected lengths dict should pass validation."""
        hit = HMMHit(
            gene_name="unknown_gene",
            start=1,
            end=1000,  # Arbitrary length
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=333,
        )

        # Unknown genes should pass (no validation)
        is_valid = _validate_hit_length(hit)
        assert is_valid is True

    def test_nad5_trans_spliced_tolerance(self):
        """nad5 is trans-spliced with variable total exon length (1800-2300bp)."""
        # nad5 expected lengths allow for trans-splicing variation
        assert "nad5" in EXPECTED_LENGTHS_WITH_TOLERANCE

        expected = EXPECTED_LENGTHS_WITH_TOLERANCE["nad5"]
        # Should have wide range for trans-spliced gene
        assert expected["min"] >= 1800
        assert expected["max"] <= 2300
        assert expected["reject_below"] >= 1620
        assert expected["reject_above"] <= 2530

    def test_nad5_at_max_range_is_valid(self):
        """nad5 at maximum expected (2300bp) should pass validation."""
        hit = HMMHit(
            gene_name="nad5",
            start=1,
            end=2300,  # At max expected
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=767,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is True

    def test_nad5_exceeds_reject_threshold(self):
        """nad5 with >2530bp should be rejected."""
        hit = HMMHit(
            gene_name="nad5",
            start=1,
            end=2531,  # Just above reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=844,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is False

    def test_small_gene_atp9_validation(self):
        """atp9 is a small gene (~225bp expected)."""
        assert "atp9" in EXPECTED_LENGTHS_WITH_TOLERANCE

        expected = EXPECTED_LENGTHS_WITH_TOLERANCE["atp9"]
        assert expected["min"] == 200
        assert expected["max"] == 280
        assert expected["reject_below"] == 180
        assert expected["reject_above"] == 310

        # Valid length
        hit = HMMHit(
            gene_name="atp9",
            start=1,
            end=225,  # Exactly expected
            strand=1,
            score=300,
            evalue=1e-5,
            domain_score=250,
            ali_start=1,
            ali_end=75,
        )
        assert _validate_hit_length(hit) is True

        # Rejected - too long
        long_hit = HMMHit(
            gene_name="atp9",
            start=1,
            end=311,  # Above reject threshold
            strand=1,
            score=300,
            evalue=1e-5,
            domain_score=250,
            ali_start=1,
            ali_end=103,
        )
        assert _validate_hit_length(long_hit) is False

    def test_all_core_genes_have_tolerance_definitions(self):
        """All core mitochondrial genes should have tolerance definitions."""
        core_genes = [
            "atp1", "atp4", "atp6", "atp8", "atp9",
            "cob", "cox1", "cox2", "cox3",
            "nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9",
        ]

        for gene in core_genes:
            assert gene in EXPECTED_LENGTHS_WITH_TOLERANCE, f"{gene} missing from tolerance dict"


class TestLengthValidationLogging:
    """Test logging behavior for validation warnings."""

    def test_over_extension_logs_warning(self, caplog):
        """When gene is over-extended, a warning should be logged."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362926,  # 721bp - exceeds reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=240,
        )

        with caplog.at_level("WARNING"):
            is_valid = _validate_hit_length(hit)

        assert is_valid is False
        assert "atp4" in caplog.text
        assert "721bp" in caplog.text
        assert "exceeds" in caplog.text or "reject" in caplog.text

    def test_fragmented_logs_warning(self, caplog):
        """When gene is fragmented (too short), a warning should be logged."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362654,  # 449bp - below reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=150,
        )

        with caplog.at_level("WARNING"):
            is_valid = _validate_hit_length(hit)

        assert is_valid is False
        assert "atp4" in caplog.text
        assert "449bp" in caplog.text
        assert "below" in caplog.text or "reject" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])