"""Mitochondrial Plastid-derived DNA Transfer detection."""

from .detector import MTPTRegion, MTPTResult, detect_mtpt, annotate_trna_origin

__all__ = ["MTPTRegion", "MTPTResult", "detect_mtpt", "annotate_trna_origin"]