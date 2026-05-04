"""Tests for the knowledge Q&A system."""

from mitoflow.ai.knowledge import KnowledgeBase


def test_get_gene_info():
    kb = KnowledgeBase()
    info = kb.get_gene_info("cox1")

    assert info["gene"] == "cox1"
    assert "product" in info
    assert "oxidase" in info["product"].lower() or "cox" in info["product"].lower()


def test_get_gene_info_with_alias():
    kb = KnowledgeBase()
    info = kb.get_gene_info("atp1")

    assert "product" in info
    assert "ATPase" in info["product"]


def test_search_genes():
    kb = KnowledgeBase()
    results = kb.search_gene("atp")

    assert len(results) > 0
    assert any("atp" in r["gene"].lower() for r in results)


def test_list_categories():
    kb = KnowledgeBase()
    categories = kb.list_categories()

    assert "core_complex_i" in categories
    assert "core_complex_iv" in categories
    assert len(categories) >= 5


def test_get_category_genes():
    kb = KnowledgeBase()
    genes = kb.get_category_genes("core_complex_i")

    assert "nad1" in [g.lower() for g in genes]
    assert len(genes) >= 5


def test_get_editing_info():
    kb = KnowledgeBase()
    info = kb.get_editing_info()

    assert "stop_gain_rna_editing" in info or "start_gain_rna_editing" in info


def test_gene_not_found():
    kb = KnowledgeBase()
    info = kb.get_gene_info("nonexistent_gene_xyz")

    assert info["gene"] == "nonexistent_gene_xyz"
    assert "product" not in info
