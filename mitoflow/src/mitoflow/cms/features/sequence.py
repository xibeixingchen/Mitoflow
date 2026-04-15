"""Classical sequence-based feature extraction for CMS candidates."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..predictor import CMSCandidate


# Kyte-Doolittle hydrophobicity values
_KD_SCALE = {
    "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5,
    "M": 1.9, "A": 1.8, "G": -0.4, "T": -0.7, "S": -0.8,
    "W": -0.9, "Y": -1.3, "P": -1.6, "H": -3.2, "E": -3.5,
    "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9, "R": -4.5,
    "X": 0.0,
}

# Approximate amino-acid molecular weights (Da)
_AA_MW = {
    "A": 89.09, "R": 174.20, "N": 132.12, "D": 133.10, "C": 121.16,
    "E": 147.13, "Q": 146.15, "G": 75.07, "H": 155.16, "I": 131.17,
    "L": 131.17, "K": 146.19, "M": 149.21, "F": 165.19, "P": 115.13,
    "S": 105.09, "T": 119.12, "W": 204.23, "Y": 181.19, "V": 117.15,
    "X": 110.0,
}

# Approximate charge at pH 7
_AA_CHARGE = {
    "D": -1.0, "E": -1.0, "K": 1.0, "R": 1.0, "H": 0.5,
}


def extract_sequence_features(candidate: "CMSCandidate") -> dict[str, float]:
    """Extract biophysical sequence features.

    Returns:
        Dict with keys: length_aa, gravy, mw, charge, aromaticity,
        n_cys, n_met, n_ser_thr, n_pos, n_neg.
    """
    seq = candidate.protein_seq.upper()
    length = len(seq)
    if length == 0:
        return {
            "length_aa": 0.0,
            "gravy": 0.0,
            "mw": 0.0,
            "charge": 0.0,
            "aromaticity": 0.0,
            "n_cys": 0.0,
            "n_met": 0.0,
            "n_ser_thr": 0.0,
            "n_pos": 0.0,
            "n_neg": 0.0,
        }

    gravy = sum(_KD_SCALE.get(aa, 0.0) for aa in seq) / length
    mw = sum(_AA_MW.get(aa, 110.0) for aa in seq)
    charge = sum(_AA_CHARGE.get(aa, 0.0) for aa in seq)
    aromaticity = sum(1 for aa in seq if aa in "FWY") / length
    n_cys = seq.count("C") / length
    n_met = seq.count("M") / length
    n_ser_thr = (seq.count("S") + seq.count("T")) / length
    n_pos = (seq.count("K") + seq.count("R")) / length
    n_neg = (seq.count("D") + seq.count("E")) / length

    return {
        "length_aa": float(length),
        "gravy": gravy,
        "mw": mw,
        "charge": charge,
        "aromaticity": aromaticity,
        "n_cys": n_cys,
        "n_met": n_met,
        "n_ser_thr": n_ser_thr,
        "n_pos": n_pos,
        "n_neg": n_neg,
    }
