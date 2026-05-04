"""Tests for wiki index and tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from mitoflow.ai.wiki.wiki_index import WikiIndex


@pytest.fixture()
def wiki() -> WikiIndex:
    return WikiIndex()


class TestWikiIndex:
    def test_load_pages(self, wiki: WikiIndex) -> None:
        assert len(wiki.pages) >= 5

    def test_search_returns_results(self, wiki: WikiIndex) -> None:
        results = wiki.search("RNA editing")
        assert len(results) > 0
        assert any("rna" in r["title"].lower() or "editing" in r["title"].lower() for r in results)

    def test_search_by_entity(self, wiki: WikiIndex) -> None:
        results = wiki.search("OrthoFinder")
        assert len(results) > 0
        assert any("OrthoFinder" in r.get("entities", []) for r in results)

    def test_search_empty_query(self, wiki: WikiIndex) -> None:
        results = wiki.search("xyznonexistent123")
        assert results == []

    def test_get_page(self, wiki: WikiIndex) -> None:
        page = wiki.get_page("rna_editing")
        assert page is not None
        assert "RNA" in page["title"]

    def test_get_page_not_found(self, wiki: WikiIndex) -> None:
        page = wiki.get_page("nonexistent_page")
        assert page is None

    def test_list_pages(self, wiki: WikiIndex) -> None:
        pages = wiki.list_pages()
        assert len(pages) >= 5
        assert all("file" in p and "title" in p for p in pages)

    def test_get_entity_pages(self, wiki: WikiIndex) -> None:
        pages = wiki.get_entity_pages("OrthoFinder")
        assert len(pages) > 0

    def test_page_has_frontmatter(self, wiki: WikiIndex) -> None:
        page = wiki.get_page("rna_editing")
        assert page is not None
        assert len(page["tags"]) > 0
        assert len(page["entities"]) > 0

    def test_search_scoring(self, wiki: WikiIndex) -> None:
        results = wiki.search("CMS")
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]
