"""Knowledge base for plant mitochondrial genomics Q&A."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).parent.parent / "data" / "gene_info"


class KnowledgeBase:
    """Structured knowledge about plant mitochondrial genes and species."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = data_dir or _DATA_DIR
        self._gene_data: Optional[Dict[str, Any]] = None
        self._species_data: Optional[List[Dict[str, str]]] = None

    @property
    def gene_data(self) -> Dict[str, Any]:
        if self._gene_data is None:
            gene_file = self._data_dir / "gene_categories.json"
            if gene_file.exists():
                with open(gene_file, encoding="utf-8") as f:
                    self._gene_data = json.load(f)
            else:
                self._gene_data = {}
        return self._gene_data

    def get_gene_info(self, gene_name: str) -> Dict[str, Any]:
        """Get comprehensive info about a gene."""
        name_lower = gene_name.lower()
        data = self.gene_data

        result: Dict[str, Any] = {"gene": gene_name}

        # Resolve alias to canonical name
        alias_map = data.get("alias_map", {})
        canonical = alias_map.get(gene_name, gene_name)
        if canonical.lower() != name_lower:
            result["canonical_name"] = canonical

        # Product name (try canonical name too)
        product_map = data.get("product_map", {})
        for key, value in product_map.items():
            if key.lower() == name_lower or key.lower() == canonical.lower():
                result["product"] = value
                if key.lower() != name_lower:
                    result["canonical_name"] = key
                break

        # Aliases (other names that resolve to the same canonical)
        aliases = [alias for alias, canon in alias_map.items() if canon.lower() == canonical.lower() and alias.lower() != name_lower]
        if aliases:
            result["aliases"] = sorted(set(aliases))

        # Category
        categories = data.get("gene_categories", {})
        for cat_name, genes in categories.items():
            if name_lower in [g.lower() for g in genes]:
                result["category"] = cat_name
                break

        # Special handling
        special = data.get("special_handling", {})
        for rule_name, rule_data in special.items():
            if isinstance(rule_data, list) and name_lower in [g.lower() for g in rule_data]:
                result.setdefault("special_rules", []).append(rule_name)
            elif isinstance(rule_data, dict):
                for sub_key, sub_val in rule_data.items():
                    if isinstance(sub_val, list) and name_lower in [g.lower() for g in sub_val]:
                        result.setdefault("special_rules", []).append(f"{rule_name}.{sub_key}")

        return result

    def get_category_genes(self, category: str) -> List[str]:
        """Get all genes in a functional category."""
        categories = self.gene_data.get("gene_categories", {})
        cat_lower = category.lower().replace(" ", "_")
        for cat_name, genes in categories.items():
            if cat_lower in cat_name.lower():
                return genes
        return []

    def list_categories(self) -> Dict[str, List[str]]:
        """List all gene categories."""
        return dict(self.gene_data.get("gene_categories", {}))

    def search_gene(self, query: str) -> List[Dict[str, Any]]:
        """Search for genes matching a query."""
        query_lower = query.lower()
        results = []
        product_map = self.gene_data.get("product_map", {})
        for gene_name, product in product_map.items():
            if gene_name.startswith("#"):
                continue
            if query_lower in gene_name.lower() or query_lower in product.lower():
                results.append({"gene": gene_name, "product": product})
        return results[:20]

    def get_splicing_info(self) -> Dict[str, Any]:
        """Get information about spliced genes."""
        special = self.gene_data.get("special_handling", {})
        result: Dict[str, Any] = {}
        for key in ["trans_splicing_genes", "cis_splicing_multi_exon"]:
            if key in special:
                result[key] = special[key]
        return result

    def get_editing_info(self) -> Dict[str, Any]:
        """Get information about RNA editing genes."""
        special = self.gene_data.get("special_handling", {})
        result: Dict[str, Any] = {}
        for key in ["stop_gain_rna_editing", "start_gain_rna_editing"]:
            if key in special:
                result[key] = special[key]
        return result
