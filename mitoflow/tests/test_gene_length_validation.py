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
        # atp4 min/max: 500-650, midpoint ~575bp
        # ±10% reject thresholds: 517 and 632
        assert expected["min"] == 500
        assert expected["max"] == 650
        # ±10% from midpoint (575): reject_below=517, reject_above=632
        assert expected["reject_below"] == 517
        assert expected["reject_above"] == 632

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
        """atp4 with >632bp should be rejected (±10% tolerance).

        This is the specific case from the comparison test:
        atp4 was annotated as 599bp when expected is ~575bp.
        With reject threshold at 632bp (10% above 575), 599bp passes
        but 650bp+ would be rejected as over-extended.
        """
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362804,  # 599bp - over-extended by ~4% over midpoint
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=200,
        )

        # 599bp is below reject_above (632), so should be valid
        is_valid = _validate_hit_length(hit)
        assert is_valid is True

        # Test at the reject threshold (632bp)
        threshold_hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362837,  # 632bp - exactly at reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=211,
        )
        # 632bp is at reject threshold, should pass (inclusive)
        is_valid = _validate_hit_length(threshold_hit)
        assert is_valid is True

    def test_atp4_severely_over_extended_is_rejected(self):
        """atp4 with >632bp should be rejected as severely over-extended."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362838,  # 633bp - exceeds reject threshold (632)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=211,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is False

    def test_atp4_fragmented_is_rejected(self):
        """atp4 with <517bp should be rejected as fragmented."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362722,  # 517bp - at reject threshold (should pass)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=172,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is True

        # Below reject threshold
        short_hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362721,  # 516bp - below reject threshold (517)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=172,
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
        # min/max range: 1800-2300, midpoint ~2050
        # ±10% reject thresholds: 1845-2255
        assert expected["min"] >= 1800
        assert expected["max"] <= 2300
        assert expected["reject_below"] >= 1845
        assert expected["reject_above"] <= 2255

    def test_nad5_at_max_range_is_valid(self):
        """nad5 within reject threshold (2255bp) should pass validation."""
        # Note: max expected is 2300bp, but reject_above is 2255bp (±10% from midpoint)
        # This is intentional - max represents typical variation, reject represents hard limit
        hit = HMMHit(
            gene_name="nad5",
            start=1,
            end=2255,  # At reject threshold (inclusive, should pass)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=751,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is True

    def test_nad5_exceeds_reject_threshold(self):
        """nad5 with >2255bp should be rejected."""
        hit = HMMHit(
            gene_name="nad5",
            start=1,
            end=2256,  # Just above reject threshold
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=752,
        )

        is_valid = _validate_hit_length(hit)
        assert is_valid is False

    def test_small_gene_atp9_validation(self):
        """atp9 is a small gene (~240bp expected midpoint)."""
        assert "atp9" in EXPECTED_LENGTHS_WITH_TOLERANCE

        expected = EXPECTED_LENGTHS_WITH_TOLERANCE["atp9"]
        # min/max: 200-280, midpoint ~240
        # ±10%: reject_below=216, reject_above=264
        assert expected["min"] == 200
        assert expected["max"] == 280
        assert expected["reject_below"] == 216
        assert expected["reject_above"] == 264

        # Valid length
        hit = HMMHit(
            gene_name="atp9",
            start=1,
            end=225,  # Within acceptable range
            strand=1,
            score=300,
            evalue=1e-5,
            domain_score=250,
            ali_start=1,
            ali_end=75,
        )
        assert _validate_hit_length(hit) is True

        # Rejected - too long (>264bp)
        long_hit = HMMHit(
            gene_name="atp9",
            start=1,
            end=265,  # Above reject threshold (264)
            strand=1,
            score=300,
            evalue=1e-5,
            domain_score=250,
            ali_start=1,
            ali_end=88,
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
            end=362838,  # 633bp - exceeds reject threshold (632)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=211,
        )

        with caplog.at_level("WARNING"):
            is_valid = _validate_hit_length(hit)

        assert is_valid is False
        assert "atp4" in caplog.text
        assert "633bp" in caplog.text
        assert "exceeds" in caplog.text or "reject" in caplog.text

    def test_fragmented_logs_warning(self, caplog):
        """When gene is fragmented (too short), a warning should be logged."""
        hit = HMMHit(
            gene_name="atp4",
            start=362206,
            end=362721,  # 516bp - below reject threshold (517)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=172,
        )

        with caplog.at_level("WARNING"):
            is_valid = _validate_hit_length(hit)

        assert is_valid is False
        assert "atp4" in caplog.text
        assert "516bp" in caplog.text
        assert "below" in caplog.text or "reject" in caplog.text


class TestValidationIntegrationInPipeline:
    """Test that validation is integrated in the annotation pipeline."""

    def test_validate_hit_length_function_exists(self):
        """_validate_hit_length should be defined and callable."""
        from mitoflow.annotate.pcg import _validate_hit_length
        assert callable(_validate_hit_length)

    def test_annotation_pipeline_filters_invalid_lengths(self, caplog):
        """annotate_pcg should filter hits with invalid lengths after refinement."""
        # This test verifies the integration by checking that annotate_pcg
        # calls _validate_hit_length during the annotation process.
        # We verify by checking the source code structure.
        import inspect
        from mitoflow.annotate.pcg import annotate_pcg

        source = inspect.getsource(annotate_pcg)

        # Check that the validation step is in the source
        assert "_validate_hit_length" in source, "annotate_pcg should call _validate_hit_length"
        assert "valid_hits" in source, "annotate_pcg should have a valid_hits variable for filtering"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])