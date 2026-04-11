"""Synteny (gene order collinearity) analysis for mitochondrial genomes.

Plant mitochondria have frequent gene rearrangements despite conserved
gene content. This module detects collinear blocks across multiple genomes.
"""

from __future__ import annotations
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SyntenyBlock:
    """A collinear block of genes shared between two species."""
    species_a: str
    species_b: str
    genes_a: list = field(default_factory=list)
    genes_b: list = field(default_factory=list)
    start_a: int = 0
    end_a: int = 0
    start_b: int = 0
    end_b: int = 0
    orientation: str = "same"  # "same" | "inverted"
    n_genes: int = 0


@dataclass
class SyntenyResult:
    """Complete synteny analysis result."""
    species_names: list = field(default_factory=list)
    gene_orders: dict = field(default_factory=dict)   # species -> [gene_names]
    gene_positions: dict = field(default_factory=dict)  # species -> {gene: (start, end)}
    synteny_blocks: list = field(default_factory=list)
    rearrangement_counts: dict = field(default_factory=dict)  # (sp_a, sp_b) -> count
    shared_genes: list = field(default_factory=list)
    unique_genes: dict = field(default_factory=dict)  # species -> [genes]
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Synteny Analysis ===",
            f"Species compared: {len(self.species_names)}",
            f"Shared genes: {len(self.shared_genes)}",
            f"Synteny blocks: {len(self.synteny_blocks)}",
        ]
        for sp, genes in self.unique_genes.items():
            if genes:
                lines.append(f"  Unique to {sp}: {', '.join(genes)}")
        for (a, b), count in self.rearrangement_counts.items():
            lines.append(f"  Rearrangements ({a} vs {b}): {count}")
        return "\n".join(lines)


def detect_synteny(
    genbank_files: list,
    species_names: Optional[list] = None,
    min_block_size: int = 2,
) -> SyntenyResult:
    """Detect synteny blocks across multiple mitochondrial genomes.

    Algorithm:
    1. Extract gene order from each GenBank file
    2. Find shared genes across all species
    3. For each pair of species, find maximal collinear blocks
    4. Count rearrangements (breakpoints between blocks)

    Args:
        genbank_files: List of GenBank file paths.
        species_names: Optional names for each species.
        min_block_size: Minimum genes per synteny block.

    Returns:
        SyntenyResult with gene orders, blocks, and rearrangement data.
    """
    from Bio import SeqIO

    result = SyntenyResult()

    n_species = len(genbank_files)
    if n_species < 2:
        result.warnings.append("Need at least 2 GenBank files for synteny")
        return result

    names = species_names or [f"species_{i}" for i in range(n_species)]
    result.species_names = names

    # Step 1: Extract gene orders
    all_gene_sets = []
    for i, gbk_path in enumerate(genbank_files):
        sp_name = names[i]
        record = next(SeqIO.parse(str(gbk_path), "genbank"))

        gene_order = []
        gene_pos = {}

        for feat in record.features:
            if feat.type not in ("gene", "CDS"):
                continue
            gname = feat.qualifiers.get("gene",
                     feat.qualifiers.get("locus_tag", [None]))[0]
            if not gname:
                continue

            # Normalize: lowercase, remove version suffixes
            gname = gname.lower().split(".")[0]
            gene_order.append(gname)
            gene_pos[gname] = (int(feat.location.start) + 1, int(feat.location.end))

        result.gene_orders[sp_name] = gene_order
        result.gene_positions[sp_name] = gene_pos
        all_gene_sets.append(set(gene_order))

    # Step 2: Find shared and unique genes
    if all_gene_sets:
        result.shared_genes = sorted(set.intersection(*all_gene_sets))
        for i, sp_name in enumerate(names):
            unique = all_gene_sets[i] - set(result.shared_genes)
            result.unique_genes[sp_name] = sorted(unique)

    # Step 3: Pairwise synteny detection
    for i in range(n_species):
        for j in range(i + 1, n_species):
            sp_a = names[i]
            sp_b = names[j]

            blocks = _find_synteny_blocks(
                result.gene_orders[sp_a],
                result.gene_orders[sp_b],
                sp_a, sp_b,
                min_block_size,
            )
            result.synteny_blocks.extend(blocks)

            # Count rearrangements (number of blocks - 1 ≈ rearrangements)
            result.rearrangement_counts[(sp_a, sp_b)] = max(0, len(blocks) - 1)

    return result


def _find_synteny_blocks(
    order_a: list,
    order_b: list,
    sp_a: str,
    sp_b: str,
    min_block_size: int,
) -> list:
    """Find collinear blocks between two gene orders.

    Uses a simple sliding-window approach:
    1. Build position index for both orders
    2. Find maximal runs of genes in the same relative order
    """
    # Build position maps
    pos_a = {gene: i for i, gene in enumerate(order_a)}
    pos_b = {gene: i for i, gene in enumerate(order_b)}

    # Find shared genes
    shared = set(order_a) & set(order_b)
    if len(shared) < min_block_size:
        return []

    # Build index pairs: for shared genes, (pos_in_a, pos_in_b)
    pairs = []
    for gene in order_a:
        if gene in shared:
            pairs.append((pos_a[gene], pos_b[gene]))

    if not pairs:
        return []

    # Find collinear blocks: maximal runs where positions increase in both
    blocks = []
    current_block = [pairs[0]]

    for k in range(1, len(pairs)):
        prev_a, prev_b = current_block[-1]
        curr_a, curr_b = pairs[k]

        # Check if same orientation (both increasing) or inverted (a increases, b decreases)
        if curr_a > prev_a:
            current_block.append(pairs[k])
        else:
            # End of block
            if len(current_block) >= min_block_size:
                blocks.append(_make_block(current_block, sp_a, sp_b, order_a, order_b, "same"))
            current_block = [pairs[k]]

    # Last block
    if len(current_block) >= min_block_size:
        blocks.append(_make_block(current_block, sp_a, sp_b, order_a, order_b, "same"))

    # Also check for inverted blocks
    inv_pairs = [(a, -b) for a, b in pairs]
    inv_pairs.sort()

    current_block_inv = [inv_pairs[0]]
    for k in range(1, len(inv_pairs)):
        prev_a, prev_b = current_block_inv[-1]
        curr_a, curr_b = inv_pairs[k]

        if curr_a > prev_a and curr_b > prev_b:
            current_block_inv.append(inv_pairs[k])
        else:
            if len(current_block_inv) >= min_block_size:
                inv_block = [(a, -b) for a, b in current_block_inv]
                blocks.append(_make_block(inv_block, sp_a, sp_b, order_a, order_b, "inverted"))
            current_block_inv = [inv_pairs[k]]

    if len(current_block_inv) >= min_block_size:
        inv_block = [(a, -b) for a, b in current_block_inv]
        blocks.append(_make_block(inv_block, sp_a, sp_b, order_a, order_b, "inverted"))

    # Deduplicate overlapping blocks
    blocks = _deduplicate_blocks(blocks)

    return blocks


def _make_block(
    pairs: list, sp_a: str, sp_b: str,
    order_a: list, order_b: str,
    orientation: str,
) -> SyntenyBlock:
    """Create a SyntenyBlock from index pairs."""
    genes_a = [order_a[p[0]] for p in pairs]
    genes_b = [order_b[p[1]] for p in pairs]

    return SyntenyBlock(
        species_a=sp_a,
        species_b=sp_b,
        genes_a=genes_a,
        genes_b=genes_b,
        start_a=pairs[0][0] + 1,
        end_a=pairs[-1][0] + 1,
        start_b=pairs[0][1] + 1,
        end_b=pairs[-1][1] + 1,
        orientation=orientation,
        n_genes=len(pairs),
    )


def _deduplicate_blocks(blocks: list) -> list:
    """Remove overlapping/duplicate blocks, keeping the largest."""
    if not blocks:
        return []

    # Sort by block size (largest first)
    blocks.sort(key=lambda b: b.n_genes, reverse=True)

    kept = []
    used_genes_a = set()
    used_genes_b = set()

    for block in blocks:
        genes_a_set = set(block.genes_a)
        genes_b_set = set(block.genes_b)

        # Check overlap
        if genes_a_set & used_genes_a or genes_b_set & used_genes_b:
            overlap_a = len(genes_a_set & used_genes_a)
            if overlap_a > block.n_genes * 0.5:
                continue  # Mostly overlapping, skip

        kept.append(block)
        used_genes_a.update(genes_a_set)
        used_genes_b.update(genes_b_set)

    return kept


def write_synteny_tables(
    result: SyntenyResult,
    output_dir: Path,
    name: str = "MitoFlow",
) -> dict:
    """Write synteny analysis results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    # Gene order table
    order_path = output_dir / f"{name}_gene_order.tsv"
    all_genes = sorted(set(g for order in result.gene_orders.values() for g in order))
    with open(order_path, "w") as f:
        header = "gene\t" + "\t".join(result.species_names) + "\n"
        f.write(header)
        for gene in all_genes:
            positions = []
            for sp in result.species_names:
                if gene in result.gene_orders[sp]:
                    idx = result.gene_orders[sp].index(gene) + 1
                    positions.append(str(idx))
                else:
                    positions.append("-")
            f.write(gene + "\t" + "\t".join(positions) + "\n")
    files["gene_order_tsv"] = order_path

    # Synteny blocks
    if result.synteny_blocks:
        blocks_path = output_dir / f"{name}_synteny_blocks.tsv"
        with open(blocks_path, "w") as f:
            f.write("sp_a\tsp_b\tgenes_a\tgenes_b\torientation\tn_genes\n")
            for block in result.synteny_blocks:
                f.write(
                    f"{block.species_a}\t{block.species_b}\t"
                    f"{','.join(block.genes_a)}\t{','.join(block.genes_b)}\t"
                    f"{block.orientation}\t{block.n_genes}\n"
                )
        files["synteny_blocks_tsv"] = blocks_path

    return files
