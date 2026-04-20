#!/usr/bin/env python3
"""Fix missing duplicate gene copies in GFF files."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.annotate.pcg import PCGConfig, _filter_duplicates, _search_hmm
from mitoflow.db.manager import DBManager
from mitoflow.models.gene import ExonRecord, Strand
from mitoflow.models.genome import GenomeSequence

logger = logging.getLogger(__name__)


@dataclass
class MockAnn:
    gene_name: str
    start: int
    end: int
    score: float
    exons: list

    @property
    def total_exon_length(self):
        return sum(e.end - e.start + 1 for e in self.exons)


VARIABLE_GENES = {"atp1", "atp6", "nad4l", "atp9", "atp8", "ccmb"}


def fix_species(fasta_file: Path, gff_file: Path):
    """Run HMM search and add missing duplicate copies to GFF."""
    if not fasta_file.exists() or not gff_file.exists():
        return False

    rec = next(SeqIO.parse(fasta_file, "fasta"))
    genome = GenomeSequence(sequence=str(rec.seq), name=rec.id, seqid=rec.id)
    db = DBManager()
    config = PCGConfig()

    hits = _search_hmm(genome, db, config)

    # Build mock annotations for _filter_duplicates
    anns = []
    for h in hits:
        strand = Strand.PLUS if h.strand == 1 else Strand.MINUS
        exon = ExonRecord(start=h.start, end=h.end, strand=strand, number=1)
        anns.append(MockAnn(gene_name=h.gene_name, start=h.start, end=h.end, score=h.score, exons=[exon]))

    filtered = _filter_duplicates(anns, config)

    # Parse existing GFF gene names
    gff_lines = gff_file.read_text().splitlines()
    existing_genes: set[str] = set()
    for line in gff_lines:
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        feat_type = parts[2]
        if feat_type != "gene":
            continue
        attrs = parts[8]
        for attr in attrs.split(";"):
            if attr.startswith("Name="):
                existing_genes.add(attr.split("=", 1)[1].lower())
                break

    # Find missing duplicate copies
    missing: list[tuple[str, MockAnn]] = []
    for key, ann in filtered.items():
        base = key.lower().split(".")[0]
        if base in VARIABLE_GENES and key.lower() not in existing_genes:
            # Check if base gene exists (e.g. atp1 exists but atp1.2 doesn't)
            if base in existing_genes:
                missing.append((key, ann))

    if not missing:
        return False

    # Add missing copies to GFF
    seqid = rec.id
    for line in gff_lines:
        if not line.startswith("#") and "\t" in line:
            seqid = line.split("\t")[0]
            break
    source = "MitoFlow"
    new_lines = []

    for key, ann in missing:
        strand = "+" if ann.exons[0].strand == Strand.PLUS else "-"
        new_lines.append(
            f"{seqid}\t{source}\tgene\t{ann.start}\t{ann.end}\t.\t{strand}\t.\t"
            f"ID={key};Name={key};Note=Duplicate copy detected by HMM (score={ann.score:.1f})"
        )
        new_lines.append(
            f"{seqid}\t{source}\tmRNA\t{ann.start}\t{ann.end}\t.\t{strand}\t.\t"
            f"ID={key}-RA;Parent={key};Name={key}"
        )
        cumulative = 0
        for i, exon in enumerate(ann.exons, 1):
            phase = cumulative % 3
            exon_strand = "+" if exon.strand == Strand.PLUS else "-"
            new_lines.append(
                f"{seqid}\t{source}\texon\t{exon.start}\t{exon.end}\t.\t{exon_strand}\t.\t"
                f"ID={key}-RA:exon:{i};Parent={key}-RA;number={i}"
            )
            new_lines.append(
                f"{seqid}\t{source}\tCDS\t{exon.start}\t{exon.end}\t.\t{exon_strand}\t{phase}\t"
                f"ID={key}-RA:cds:{i};Parent={key}-RA"
            )
            cumulative += exon.end - exon.start + 1
        logger.info(
            f"Added {key} ({ann.start}-{ann.end}, score={ann.score:.1f})"
        )

    # Append new lines to GFF
    gff_file.write_text("\n".join(gff_lines + new_lines) + "\n")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gff-dir", default="results/phase3_quick_batch")
    parser.add_argument("--fasta-dir", default="data/gold_standard/fasta")
    parser.add_argument("--species-list", default="data/gold_standard/species_list.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    import pandas as pd

    species_df = pd.read_csv(args.species_list)
    gff_dir = Path(args.gff_dir)
    fasta_dir = Path(args.fasta_dir)
    changed_any = False

    for _, row in species_df.iterrows():
        species_name = row["species"]
        species_safe = species_name.replace(" ", "_").replace(".", "").replace("'", "")
        fasta = fasta_dir / f"{species_name}.fasta"
        if not fasta.exists():
            alt_fastas = list(fasta_dir.glob(f"{species_safe}*.fasta"))
            if alt_fastas:
                fasta = alt_fastas[0]
        gff = gff_dir / species_safe / "gff" / f"{species_safe}.gff"
        changed = fix_species(fasta, gff)
        changed_any = changed_any or changed

    if changed_any:
        logger.info("GFF files updated with missing duplicate copies.")
    else:
        logger.info("No missing duplicate copies found.")


if __name__ == "__main__":
    main()
