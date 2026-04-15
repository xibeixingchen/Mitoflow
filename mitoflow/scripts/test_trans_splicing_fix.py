#!/usr/bin/env python3
"""Quick test for trans-spliced gene boundary fixes."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.models.genome import GenomeSequence
from mitoflow.db.manager import DBManager
from mitoflow.annotate.trans_splicing import annotate_trans_spliced_genes
from Bio import SeqIO

def load_current_annotations(gb_path: Path):
    """Load gene annotations from existing GenBank file."""
    from mitoflow.models.gene import GeneAnnotation, ExonRecord, Strand
    anns = {}
    rec = next(SeqIO.parse(gb_path, "genbank"))
    for feat in rec.features:
        if feat.type == "CDS":
            gene_name = feat.qualifiers.get("gene", [""])[0].lower()
            if not gene_name:
                continue
            exons = []
            strand = Strand.MINUS if feat.location.strand == -1 else Strand.PLUS
            for i, loc in enumerate(feat.location.parts, 1):
                exons.append(ExonRecord(start=int(loc.start) + 1, end=int(loc.end), strand=strand, number=i))
            ann = GeneAnnotation(
                gene_name=gene_name,
                exons=exons,
                strand=strand,
                product=feat.qualifiers.get("product", [""])[0],
                transl_table=1,
                source_method="HMM",
            )
            anns[gene_name] = ann
    return anns


def test_species(name: str, fasta_path: Path, gb_path: Path):
    print(f"\n=== {name} ===")
    rec = next(SeqIO.parse(fasta_path, "fasta"))
    seq = str(rec.seq)
    genome = GenomeSequence(sequence=seq, name=name, seqid=rec.id)
    db = DBManager()

    current = load_current_annotations(gb_path)
    for gene in ["nad1", "nad7", "cox2"]:
        if gene in current:
            g = current[gene]
            print(f"Before: {gene} exons = {[(e.start, e.end) for e in g.exons]}")
        else:
            print(f"Before: {gene} not found")

    updated = annotate_trans_spliced_genes(genome, db, current)

    for gene in ["nad1", "nad7", "cox2"]:
        if gene in updated:
            g = updated[gene]
            print(f"After:  {gene} exons = {[(e.start, e.end) for e in g.exons]}")
        else:
            print(f"After:  {gene} not found")


if __name__ == "__main__":
    test_species(
        "Glycine_max",
        Path("data/gold_standard/fasta/Glycine_max.fasta"),
        Path("results/phase2_full_batch/Glycine_max/genbank/Glycine_max.gb"),
    )
    test_species(
        "Liriodendron_tulipifera",
        Path("data/gold_standard/fasta/Liriodendron_tulipifera.fasta"),
        Path("results/phase2_full_batch/Liriodendron_tulipifera/genbank/Liriodendron_tulipifera.gb"),
    )
    test_species(
        "Nymphaea",
        Path("data/gold_standard/fasta/Nymphaea_hybrid_cultivar_'Joey_Tomocik'.fasta"),
        Path("results/phase2_full_batch/Nymphaea_hybrid_cultivar_'Joey_Tomocik'/genbank/Nymphaea_hybrid_cultivar_'Joey_Tomocik'.gb"),
    )
