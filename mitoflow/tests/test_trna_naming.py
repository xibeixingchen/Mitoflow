"""Tests for tRNA naming convention standardization.

This module tests that MitoFlow tRNA naming is compatible with NCBI format.
NCBI uses: trnI(cau) - lowercase T notation in parentheses
MitoFlow was using: trnI-AAU - uppercase U notation with hyphen
"""
import pytest
from mitoflow.annotate.trna import (
    _parse_trna_name,
    _standardize_trna_name,
    RawTRNA,
    _parse_trnascan_output,
    _parse_aragorn_output,
)


class TestStandardizeTRnaName:
    """Tests for _standardize_trna_name function."""

    def test_u_to_t_conversion(self):
        """Anticodon U should be converted to T."""
        result = _standardize_trna_name("I", "AAU")
        assert result == "trnI(aat)", f"Expected 'trnI(aat)', got '{result}'"

    def test_lowercase_output(self):
        """Anticodon should be lowercase in output."""
        result = _standardize_trna_name("F", "GAA")
        assert result == "trnF(gaa)", f"Expected 'trnF(gaa)', got '{result}'"

    def test_parentheses_format(self):
        """Name should use parentheses, not hyphen."""
        result = _standardize_trna_name("M", "CAU")
        assert "(" in result and ")" in result, f"Expected parentheses in '{result}'"
        assert "-" not in result, f"Hyphen should not be in '{result}'"

    def test_standard_ncbi_format(self):
        """Test standard NCBI format examples."""
        test_cases = [
            ("I", "AAU", "trnI(aat)"),  # U -> T conversion
            ("F", "GAA", "trnF(gaa)"),  # No U, stays same
            ("M", "CAU", "trnM(cat)"),  # U -> T conversion
            ("W", "CCA", "trnW(cca)"),  # No U, stays same
            ("L", "UAA", "trnL(taa)"),  # U -> T conversion (Leu with UAA anticodon)
            ("S", "GCU", "trnS(gct)"),  # U -> T conversion (Ser with GCU anticodon)
        ]
        for aa, anticodon, expected in test_cases:
            result = _standardize_trna_name(aa, anticodon)
            assert result == expected, f"For {aa}/{anticodon}: expected '{expected}', got '{result}'"

    def test_mixed_case_input(self):
        """Should handle mixed case input."""
        result = _standardize_trna_name("i", "aau")
        assert result == "trnI(aat)", f"Expected 'trnI(aat)', got '{result}'"

    def test_fmet_standardization(self):
        """fMet (formylmethionine) should be standardized to 'M' (Met)."""
        result = _standardize_trna_name("fMet", "CAU")
        assert result == "trnM(cat)", f"Expected 'trnM(cat)', got '{result}'"

    def test_fmet_case_insensitive(self):
        """fMet handling should be case-insensitive."""
        test_cases = ["fMet", "fmet", "FMET", "Fmet"]
        for fmet_input in test_cases:
            result = _standardize_trna_name(fmet_input, "CAU")
            assert result == "trnM(cat)", f"For '{fmet_input}': expected 'trnM(cat)', got '{result}'"


class TestTRnaNamingIntegration:
    """Integration tests for tRNA naming in the pipeline."""

    def test_trna_name_matches_ncbi_format(self):
        """tRNA names should use NCBI-compatible format: trnI(cau)."""
        # Create a RawTRNA with standardized name
        gene_name = _standardize_trna_name("I", "AAU")
        mito_trna = RawTRNA(
            gene_name=gene_name,
            start=1000, end=1070, strand=1,
            anticodon="AAT",  # T notation
            amino_acid="I",
            score=50, source="ARAGORN",
        )

        # NCBI format for comparison
        ncbi_name = "trnI(aat)"

        assert mito_trna.gene_name.lower() == ncbi_name.lower(), \
            f"Expected {ncbi_name}, got {mito_trna.gene_name}"

    def test_anticodon_normalization_for_comparison(self):
        """Anticodon U should be normalized to T for comparison."""
        u_anticodon = "AAU"
        t_anticodon = "AAT"

        # When creating standardized name, U should become T
        gene_name = _standardize_trna_name("I", u_anticodon)
        assert "aat" in gene_name.lower(), f"Expected 'aat' in {gene_name}"

        # Direct normalization
        normalized = u_anticodon.upper().replace("U", "T")
        assert normalized == t_anticodon


class TestParseTRnaName:
    """Tests for _parse_trna_name function."""

    def test_parse_standard_format(self):
        """Parse trnX(abc) format."""
        aa, anticodon = _parse_trna_name("trnI(aat)")
        assert aa == "I", f"Expected 'I', got '{aa}'"
        assert anticodon == "AAT", f"Expected 'AAT', got '{anticodon}'"

    def test_parse_hyphen_format(self):
        """Parse trnX-ABC format (legacy)."""
        aa, anticodon = _parse_trna_name("trnI-AAU")
        assert aa == "I", f"Expected 'I', got '{aa}'"
        assert anticodon == "AAU", f"Expected 'AAU', got '{anticodon}'"

    def test_parse_reference_id(self):
        """Parse reference sequence ID format."""
        aa, anticodon = _parse_trna_name("RefVi3086_tRNA_trnA-UGC_0001")
        assert aa == "A", f"Expected 'A', got '{aa}'"
        assert anticodon == "UGC", f"Expected 'UGC', got '{anticodon}'"

    def test_parse_full_aa_name(self):
        """Parse full amino acid names like 'Ala', 'Cys'."""
        aa, anticodon = _parse_trna_name("tRNA_Ala_001")
        assert aa == "A", f"Expected 'A', got '{aa}'"


class TestRoundTrip:
    """Test that we can parse and regenerate tRNA names."""

    def test_roundtrip_ncbi_format(self):
        """Parse NCBI format and regenerate it."""
        original = "trnI(aat)"
        aa, anticodon = _parse_trna_name(original)
        regenerated = _standardize_trna_name(aa, anticodon)
        assert regenerated == original, f"Round-trip failed: {original} -> {regenerated}"

    def test_roundtrip_legacy_format(self):
        """Parse legacy format and convert to NCBI format."""
        legacy = "trnI-AAU"  # U notation, hyphen
        aa, anticodon = _parse_trna_name(legacy)
        # After standardization, should be NCBI format
        standardized = _standardize_trna_name(aa, anticodon)
        expected = "trnI(aat)"  # T notation, parentheses
        assert standardized == expected, f"Expected {expected}, got {standardized}"
