#!/usr/bin/env python3
"""Apply trans-splicing fixes directly to existing GFF files."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.annotate.trans_splicing import annotate_trans_spliced_genes
from mitoflow.db.manager import DBManager
from mitoflow.models.genome import GenomeSequence

logger = logging.getLogger(__name__)

SPECIES = [
    ("Nymphaea_hybrid_cultivar_'Joey_Tomocik'", "MW644617.1"),
    ("Selenicereus_monacanthus", "OQ835513.1"),
    ("Eucommia_ulmoides", "OQ101613.1"),
    ("Capsicum_annuum_cultivar_Jeju", "NC_024624.1"),
    ("Liriodendron_tulipifera", "NC_021152.1"),
    ("Glycine_max", "NC_020455.1"),
    ("Pontederia_crassipes", "OR680719.1"),
    ("Camellia_sinensis_var_assamica", "MK574876.1"),
]


def apply_fix(species_name: str, fasta_path: Path, gff_path: Path):
    """Run annotate_trans_spliced_genes on existing annotations and update GFF."""
    if not fasta_path.exists():
        logger.warning(f"FASTA not found: {fasta_path}")
        return False
    if not gff_path.exists():
        logger.warning(f"GFF not found: {gff_path}")
        return False

    rec = next(SeqIO.parse(fasta_path, "fasta"))
    genome = GenomeSequence(sequence=str(rec.seq), name=species_name, seqid=rec.id)
    db = DBManager()

    # Parse existing GFF into annotation dict using grep for speed
    gff_lines = gff_path.read_text().splitlines()

    # Build a map: gene_name -> list of (line_index, line)
    gene_blocks: dict[str, list[tuple[int, str]]] = {}
    gene_of_line: dict[int, str] = {}
    for i, line in enumerate(gff_lines):
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        attrs = parts[8]
        gene_name = ""
        parent = ""
        for attr in attrs.split(";"):
            if "=" in attr:
                k, v = attr.split("=", 1)
                if k == "Name":
                    gene_name = v.lower()
                elif k == "Parent":
                    parent = v
        if not gene_name and parent:
            gene_name = parent.split("-")[0].lower()
        if gene_name:
            gene_blocks.setdefault(gene_name, []).append((i, line))
            gene_of_line[i] = gene_name

    # No need to fully reconstruct annotations; we just:
    # 1. Remove old lines for genes that will be updated
    # 2. Run annotate_trans_spliced_genes with empty dict so it builds from scratch
    #    (since trans_splicing works best when not constrained by existing HMM boundaries)
    updated = annotate_trans_spliced_genes(genome, db, {})

    changed = False
    updated_lines = list(gff_lines)
    # Indices to remove (in reverse order)
    to_remove: set[int] = set()

    genes_to_update = {"cox2", "nad1", "nad7"}
    for gene_name in genes_to_update:
        if gene_name not in updated:
            continue
        ann = updated[gene_name]
        if gene_name not in gene_blocks:
            logger.info(f"{species_name}: {gene_name} not in existing GFF, skipping")
            continue

        # Mark old lines for removal
        for idx, _line in gene_blocks[gene_name]:
            to_remove.add(idx)

        # Build new GFF block
        seqid = species_name.replace(" ", "_").replace(".", "")
        source = "MitoFlow"
        strand = ann.strand.symbol
        gene_start = min(e.start for e in ann.exons)
        gene_end = max(e.end for e in ann.exons)

        new_block = []
        # gene feature
        note = "Merged from {} exons via BLASTn".format(len(ann.exons))
        new_block.append(
            f"{seqid}\t{source}\tgene\t{gene_start}\t{gene_end}\t.\t{strand}\t.\t"
            f"ID={ann.gene_name};Name={ann.gene_name};product={ann.product or ann.gene_name};Note={note}"
        )
        # mRNA feature
        new_block.append(
            f"{seqid}\t{source}\tmRNA\t{gene_start}\t{gene_end}\t.\t{strand}\t.\t"
            f"ID={ann.gene_name}-RA;Parent={ann.gene_name};Name={ann.gene_name}"
        )
        # exon + CDS features
        cumulative_len = 0
        for i, exon in enumerate(ann.exons, 1):
            phase = cumulative_len % 3
            new_block.append(
                f"{seqid}\t{source}\texon\t{exon.start}\t{exon.end}\t.\t{exon.strand.symbol}\t.\t"
                f"ID={ann.gene_name}-RA:exon:{i};Parent={ann.gene_name}-RA;number={i}"
            )
            new_block.append(
                f"{seqid}\t{source}\tCDS\t{exon.start}\t{exon.end}\t.\t{exon.strand.symbol}\t{phase}\t"
                f"ID={ann.gene_name}-RA:cds:{i};Parent={ann.gene_name}-RA"
            )
            cumulative_len += exon.end - exon.start + 1

        # Insert new block at the position of the first removed line
        if gene_blocks[gene_name]:
            first_idx = gene_blocks[gene_name][0][0]
            updated_lines[first_idx] = "\n".join(new_block)
            for idx in sorted(to_remove):
                if idx != first_idx:
                    updated_lines[idx] = ""
            changed = True
            logger.info(
                f"{species_name}: updated {gene_name} to {len(ann.exons)} exons "
                f"({gene_start}-{gene_end})"
            )

    if changed:
        gff_path.write_text("\n".join(line for line in updated_lines if line != "") + "\n")
    return changed


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    fasta_dir = Path("data/gold_standard/fasta")
    gff_dir = Path("results/phase4_boundary_fix")
    changed_any = False

    for species_name, _acc in SPECIES:
        fasta = fasta_dir / f"{species_name}.fasta"
        gff = gff_dir / species_name.replace(" ", "_").replace(".", "").replace("'", "") / "gff" / f"{species_name.replace(' ', '_').replace('.', '').replace(chr(39), '')}.gff"
        changed = apply_fix(species_name, fasta, gff)
        changed_any = changed_any or changed

    if changed_any:
        logger.info("GFF files updated. Run validation script to evaluate.")
    else:
        logger.info("No changes applied.")


if __name__ == "__main__":
    main()
