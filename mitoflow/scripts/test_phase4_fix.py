#!/usr/bin/env python3
"""Quick test for Phase 4 trans-splicing fixes."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.models.genome import GenomeSequence
from mitoflow.models.gene import GeneAnnotation, ExonRecord, Strand
from mitoflow.db.manager import DBManager
from mitoflow.annotate.trans_splicing import annotate_trans_spliced_genes
from Bio import SeqIO


def load_gff_annotations(gff_path: Path) -> dict[str, GeneAnnotation]:
    """Load gene annotations from MitoFlow GFF file."""
    anns: dict[str, GeneAnnotation] = {}
    exons: dict[str, list[ExonRecord]] = {}
    gene_strands: dict[str, Strand] = {}
    if not gff_path.exists():
        return anns
    for line in gff_path.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9 or parts[2] not in ("CDS", "exon"):
            continue
        start = int(parts[3])
        end = int(parts[4])
        strand = Strand.MINUS if parts[6] == "-" else Strand.PLUS
        attrs = parts[8]
        gene_name = ""
        for attr in attrs.split(";"):
            if "=" in attr:
                k, v = attr.split("=", 1)
                if k == "Name":
                    gene_name = v.lower()
        if not gene_name:
            continue
        if parts[2] == "exon":
            exons.setdefault(gene_name, []).append(
                ExonRecord(start=start, end=end, strand=strand, number=0)
            )
            gene_strands[gene_name] = strand
    for gene_name, gene_exons in exons.items():
        gene_exons.sort(key=lambda e: e.start)
        for i, e in enumerate(gene_exons, 1):
            e.number = i
        anns[gene_name] = GeneAnnotation(
            gene_name=gene_name,
            exons=gene_exons,
            strand=gene_strands.get(gene_name, Strand.PLUS),
            source_method="HMM",
        )
    return anns


def test_species(name: str, fasta_path: Path, gff_path: Path):
    print(f"\n=== {name} ===")
    rec = next(SeqIO.parse(fasta_path, "fasta"))
    seq = str(rec.seq)
    genome = GenomeSequence(sequence=seq, name=name, seqid=rec.id)
    db = DBManager()

    current = load_gff_annotations(gff_path)
    for gene in ["nad1", "nad7", "cox2"]:
        if gene in current:
            g = current[gene]
            coord_list = [(e.start, e.end, e.strand.symbol) for e in g.exons]
            print(f"Before: {gene} exons = {coord_list}")
        else:
            print(f"Before: {gene} not found")

    updated = annotate_trans_spliced_genes(genome, db, current)

    changed = False
    for gene in ["nad1", "nad7", "cox2"]:
        if gene in updated:
            g = updated[gene]
            coord_list = [(e.start, e.end, e.strand.symbol) for e in g.exons]
            print(f"After:  {gene} exons = {coord_list}")
            if gene in current and len(g.exons) != len(current[gene].exons):
                print(f"  *** EXON COUNT CHANGED ***")
                changed = True
            if gene in current:
                for i, (old, new) in enumerate(zip(current[gene].exons, g.exons)):
                    if old.start != new.start or old.end != new.end:
                        print(f"  *** BOUNDARY CHANGED for exon {i+1}: {old.start}-{old.end} -> {new.start}-{new.end} ***")
                        changed = True
        else:
            print(f"After:  {gene} not found")
    return changed


if __name__ == "__main__":
    species_list = [
        ("Nymphaea", Path("data/gold_standard/fasta/Nymphaea_hybrid_cultivar_'Joey_Tomocik'.fasta"), Path("results/phase4_boundary_fix/Nymphaea_hybrid_cultivar_Joey_Tomocik/gff/Nymphaea_hybrid_cultivar_Joey_Tomocik.gff")),
        ("Selenicereus", Path("data/gold_standard/fasta/Selenicereus_monacanthus.fasta"), Path("results/phase4_boundary_fix/Selenicereus_monacanthus/gff/Selenicereus_monacanthus.gff")),
        ("Eucommia", Path("data/gold_standard/fasta/Eucommia_ulmoides.fasta"), Path("results/phase4_boundary_fix/Eucommia_ulmoides/gff/Eucommia_ulmoides.gff")),
        ("Capsicum", Path("data/gold_standard/fasta/Capsicum_annuum_cultivar_Jeju.fasta"), Path("results/phase4_boundary_fix/Capsicum_annuum_cultivar_Jeju/gff/Capsicum_annuum_cultivar_Jeju.gff")),
        ("Liriodendron", Path("data/gold_standard/fasta/Liriodendron_tulipifera.fasta"), Path("results/phase4_boundary_fix/Liriodendron_tulipifera/gff/Liriodendron_tulipifera.gff")),
    ]
    any_changed = False
    for name, fasta, gff in species_list:
        changed = test_species(name, fasta, gff)
        any_changed = any_changed or changed
    print(f"\n{'='*40}")
    if any_changed:
        print("Changes detected — need to regenerate GFFs.")
    else:
        print("No exon count / boundary changes detected.")
