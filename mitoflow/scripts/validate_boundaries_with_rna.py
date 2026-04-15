#!/usr/bin/env python3
"""Validate disputed gene boundaries using RNA-seq coverage and splice junctions."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from Bio import SeqIO

logger = logging.getLogger(__name__)

BAM_DIR = Path("data/rna_seq/bam")
JUNC_DIR = Path("data/rna_seq/junctions")
MITOFLOW_GFF_DIR = Path("results/phase3_quick_batch")
NCBI_GB_DIR = Path("data/gold_standard/genbank")
OUTPUT_DIR = Path("results/rna_validation")

# Target genes with frequent boundary disputes
TARGET_GENES = {
    "cox2", "nad5", "nad1", "nad2", "nad4", "nad7",
    "rpl16", "atp6", "cox3", "rps4", "rps3",
}


def find_ncbi_genbank(species_name: str) -> Path | None:
    """Find NCBI GenBank file by looking up accession in species_list.csv."""
    import pandas as pd
    species_list = Path("data/gold_standard/species_list.csv")
    if not species_list.exists():
        return None
    df = pd.read_csv(species_list)
    row = df[df["species"].str.strip().str.lower() == species_name.lower().strip()]
    if row.empty:
        return None
    genbank_acc = str(row.iloc[0]["genbank"]).strip()
    for acc in genbank_acc.replace(";", ",").split(","):
        acc = acc.strip()
        gb_file = NCBI_GB_DIR / f"{acc}.gb"
        if gb_file.exists():
            return gb_file
    return None


def load_ncbi_cds_coords(genbank_file: Path) -> Dict[str, Tuple[int, int, str, List[Tuple[int, int]]]]:
    """Load CDS coordinates from NCBI GenBank.

    Returns dict: gene_name -> (start, end, strand, [(exon_start, exon_end), ...])
    """
    coords = {}
    try:
        records = list(SeqIO.parse(genbank_file, "genbank"))
    except Exception as e:
        logger.warning(f"Failed to parse {genbank_file}: {e}")
        return coords

    for record in records:
        for feat in record.features:
            if feat.type != "CDS":
                continue
            gene_name = ""
            if "gene" in feat.qualifiers:
                gene_name = feat.qualifiers["gene"][0].lower()
            elif "product" in feat.qualifiers:
                gene_name = feat.qualifiers["product"][0].lower().split()[0]
            if not gene_name or gene_name not in TARGET_GENES:
                continue

            strand = "+" if feat.location.strand == 1 else "-"
            exons = []
            for part in feat.location.parts:
                exons.append((int(part.start) + 1, int(part.end)))
            start = min(e[0] for e in exons)
            end = max(e[1] for e in exons)
            coords[gene_name] = (start, end, strand, exons)
    return coords


def load_mitoflow_cds_coords(gff_file: Path) -> Dict[str, Tuple[int, int, str, List[Tuple[int, int]]]]:
    """Load CDS coordinates from MitoFlow GFF.

    Returns dict: gene_name -> (start, end, strand, [(exon_start, exon_end), ...])
    """
    coords = {}
    exons = defaultdict(list)

    if not gff_file.exists():
        return coords

    for line in gff_file.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        if parts[2] not in ("CDS", "exon"):
            continue

        start = int(parts[3])
        end = int(parts[4])
        strand = parts[6]

        # Parse attributes
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

        # Use Name if present; otherwise try to infer from Parent
        if not gene_name and parent:
            gene_name = parent.split("-")[0].lower()

        if not gene_name or gene_name not in TARGET_GENES:
            continue

        if parts[2] == "exon":
            exons[gene_name].append((start, end, strand))

    for gene_name, gene_exons in exons.items():
        strand = gene_exons[0][2]
        starts_ends = [(e[0], e[1]) for e in gene_exons]
        start = min(e[0] for e in starts_ends)
        end = max(e[1] for e in starts_ends)
        coords[gene_name] = (start, end, strand, starts_ends)

    return coords


def get_bam_ref_name(bam_path: Path) -> str:
    """Extract the first reference sequence name from BAM header."""
    try:
        proc = subprocess.run(
            ["samtools", "view", "-H", str(bam_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        for line in proc.stdout.split("\n"):
            if line.startswith("@SQ"):
                for field in line.split("\t"):
                    if field.startswith("SN:"):
                        return field[3:]
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to read BAM header for {bam_path}: {e}")
    return ""


def get_region_depth(bam_path: Path, chrom: str, start: int, end: int) -> Dict[int, int]:
    """Return per-base depth in region using samtools depth."""
    depth: Dict[int, int] = {}
    # Use actual BAM ref name if it differs from provided chrom
    actual_chrom = get_bam_ref_name(bam_path) or chrom
    try:
        proc = subprocess.run(
            ["samtools", "depth", "-r", f"{actual_chrom}:{start}-{end}", str(bam_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        for line in proc.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                pos = int(parts[1])
                depth[pos] = int(parts[2])
    except subprocess.CalledProcessError as e:
        logger.warning(f"samtools depth failed for {bam_path}: {e}")
    return depth


def load_junctions(junc_path: Path) -> Dict[Tuple[str, int, int, str], int]:
    """Load junction BED into dict."""
    junctions = {}
    if not junc_path.exists():
        return junctions
    for line in junc_path.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        chrom = parts[0]
        start = int(parts[1]) + 1  # BED 0-based to 1-based
        end = int(parts[2])
        strand = parts[5]
        count = int(parts[4])
        junctions[(chrom, start, end, strand)] = count
    return junctions


def evaluate_boundary(
    gene_name: str,
    ncbi_exons: List[Tuple[int, int]],
    mito_exons: List[Tuple[int, int]],
    depth: Dict[int, int],
    junctions: Dict[Tuple[str, int, int, str], int],
    chrom: str,
    strand: str,
) -> Dict:
    """Compare NCBI vs MitoFlow boundaries using RNA evidence."""
    result = {
        "gene": gene_name,
        "verdict": "ambiguous",
        "details": [],
        "mitoflow_support": 0,
        "ncbi_support": 0,
    }

    if len(ncbi_exons) != len(mito_exons):
        result["details"].append(
            f"Exon count mismatch: NCBI={len(ncbi_exons)}, MitoFlow={len(mito_exons)}"
        )

    max_exons = max(len(ncbi_exons), len(mito_exons))
    for i in range(max_exons - 1):
        # Intron boundary comparison
        ncbi_donor = ncbi_exons[i][1] if i < len(ncbi_exons) else None
        ncbi_acceptor = ncbi_exons[i + 1][0] if (i + 1) < len(ncbi_exons) else None
        mito_donor = mito_exons[i][1] if i < len(mito_exons) else None
        mito_acceptor = mito_exons[i + 1][0] if (i + 1) < len(mito_exons) else None

        if ncbi_donor is None or mito_donor is None:
            continue

        # Fuzzy junction lookup allowing +/- 2 bp wobble
        def _lookup_junc(donor: int, acceptor: int) -> int:
            total = 0
            for d_off in range(-2, 3):
                for a_off in range(-2, 3):
                    total += junctions.get((chrom, donor + d_off, acceptor + a_off, strand), 0)
            return total

        ncbi_junc_count = _lookup_junc(ncbi_donor, ncbi_acceptor) if ncbi_donor and ncbi_acceptor else 0
        mito_junc_count = _lookup_junc(mito_donor, mito_acceptor) if mito_donor and mito_acceptor else 0

        result["ncbi_support"] += ncbi_junc_count
        result["mitoflow_support"] += mito_junc_count

        if ncbi_donor == mito_donor and ncbi_acceptor == mito_acceptor:
            if ncbi_junc_count >= 5:
                result["details"].append(
                    f"Intron {i+1}: identical boundaries with strong junction support (n={ncbi_junc_count})"
                )
            else:
                result["details"].append(f"Intron {i+1}: identical boundaries (n={ncbi_junc_count})")
        elif mito_junc_count >= 5 and ncbi_junc_count < 2:
            result["details"].append(
                f"Intron {i+1}: strong junction support for MitoFlow "
                f"({mito_donor}-{mito_acceptor}, n={mito_junc_count}) vs NCBI ({ncbi_donor}-{ncbi_acceptor}, n={ncbi_junc_count})"
            )
        elif ncbi_junc_count >= 5 and mito_junc_count < 2:
            result["details"].append(
                f"Intron {i+1}: strong junction support for NCBI "
                f"({ncbi_donor}-{ncbi_acceptor}, n={ncbi_junc_count}) vs MitoFlow ({mito_donor}-{mito_acceptor}, n={mito_junc_count})"
            )
        else:
            result["details"].append(
                f"Intron {i+1}: ambiguous junction support "
                f"MitoFlow n={mito_junc_count}, NCBI n={ncbi_junc_count}"
            )

    # Terminal boundary coverage check
    if len(mito_exons) > 0 and len(ncbi_exons) > 0:
        # Last exon end
        mito_end = mito_exons[-1][1]
        ncbi_end = ncbi_exons[-1][1]
        if mito_end != ncbi_end:
            # Check if coverage drops between the two ends
            region_start = min(mito_end, ncbi_end)
            region_end = max(mito_end, ncbi_end)
            if region_end - region_start <= 100:
                mid_depths = [depth.get(p, 0) for p in range(region_start, region_end + 1)]
                avg_depth = sum(mid_depths) / len(mid_depths) if mid_depths else 0
                if avg_depth < 5:
                    result["details"].append(
                        f"Stop boundary: low coverage in disputed region ({region_start}-{region_end}, avg_depth={avg_depth:.1f})"
                    )
                else:
                    result["details"].append(
                        f"Stop boundary: continuous coverage in disputed region ({region_start}-{region_end}, avg_depth={avg_depth:.1f})"
                    )

        # First exon start
        mito_start = mito_exons[0][0]
        ncbi_start = ncbi_exons[0][0]
        if mito_start != ncbi_start:
            region_start = min(mito_start, ncbi_start)
            region_end = max(mito_start, ncbi_start)
            if region_end - region_start <= 100:
                mid_depths = [depth.get(p, 0) for p in range(region_start, region_end + 1)]
                avg_depth = sum(mid_depths) / len(mid_depths) if mid_depths else 0
                if avg_depth < 5:
                    result["details"].append(
                        f"Start boundary: low coverage in disputed region ({region_start}-{region_end}, avg_depth={avg_depth:.1f})"
                    )
                else:
                    result["details"].append(
                        f"Start boundary: continuous coverage in disputed region ({region_start}-{region_end}, avg_depth={avg_depth:.1f})"
                    )

    # Overall verdict
    if result["mitoflow_support"] >= 10 and result["ncbi_support"] < 3:
        result["verdict"] = "strong_support_mitoflow"
    elif result["ncbi_support"] >= 10 and result["mitoflow_support"] < 3:
        result["verdict"] = "strong_support_ncbi"
    elif result["mitoflow_support"] == 0 and result["ncbi_support"] == 0:
        result["verdict"] = "no_rna_evidence"
    else:
        result["verdict"] = "ambiguous"

    return result


def validate_species(species_name: str, bam_files: List[Path], junc_files: List[Path]) -> Dict:
    """Validate one species across all available BAMs."""
    species_safe = species_name.replace(" ", "_").replace(".", "").replace("'", "")

    ncbi_gb = find_ncbi_genbank(species_name)
    if not ncbi_gb:
        # Fallback to filename-based search
        ncbi_gb = NCBI_GB_DIR / f"{species_safe}.gb"
        if not ncbi_gb.exists():
            candidates = list(NCBI_GB_DIR.glob(f"*{species_safe}*.gb"))
            if candidates:
                ncbi_gb = candidates[0]

    mitoflow_gff_dir = MITOFLOW_GFF_DIR / species_safe / "gff"
    mitoflow_gff = mitoflow_gff_dir / f"{species_safe}.gff"
    if not mitoflow_gff.exists():
        # Fallback: search for directory matching species name
        for candidate_dir in MITOFLOW_GFF_DIR.iterdir():
            if candidate_dir.is_dir() and species_name.replace(" ", "_").lower() in candidate_dir.name.lower():
                gff_dir = candidate_dir / "gff"
                for gff in gff_dir.glob("*.gff"):
                    mitoflow_gff = gff
                    break
                if mitoflow_gff.exists():
                    break

    ncbi_coords = load_ncbi_cds_coords(ncbi_gb)
    mito_coords = load_mitoflow_cds_coords(mitoflow_gff)

    results = []
    common_genes = set(ncbi_coords.keys()) & set(mito_coords.keys()) & TARGET_GENES

    # Merge junctions from all SRRs
    all_junctions: Dict[Tuple[str, int, int, str], int] = defaultdict(int)
    for jf in junc_files:
        juncs = load_junctions(jf)
        for k, v in juncs.items():
            all_junctions[k] += v

    # Use first BAM for depth queries (or merge depth across all BAMs)
    primary_bam = bam_files[0] if bam_files else None
    actual_chrom = get_bam_ref_name(primary_bam) if primary_bam else species_safe

    for gene in sorted(common_genes):
        ncbi_start, ncbi_end, ncbi_strand, ncbi_exons = ncbi_coords[gene]
        mito_start, mito_end, mito_strand, mito_exons = mito_coords[gene]

        # Skip if strand differs (annotation mismatch)
        if ncbi_strand != mito_strand:
            results.append({
                "gene": gene,
                "verdict": "strand_mismatch",
                "details": [f"NCBI strand={ncbi_strand}, MitoFlow strand={mito_strand}"],
            })
            continue

        region_start = min(ncbi_start, mito_start) - 50
        region_end = max(ncbi_end, mito_end) + 50
        depth = {}
        if primary_bam:
            depth = get_region_depth(primary_bam, actual_chrom, region_start, region_end)

        eval_result = evaluate_boundary(
            gene, ncbi_exons, mito_exons, depth, dict(all_junctions), actual_chrom, ncbi_strand
        )
        results.append(eval_result)

    return {
        "species": species_name,
        "genes_evaluated": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate gene boundaries with RNA-seq")
    parser.add_argument("--species", help="Validate a single species")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    import pandas as pd
    SPECIES_LIST = Path("data/gold_standard/species_list.csv")
    DEFAULT_TARGET_SPECIES = [
        "Camellia sinensis var. assamica",
        "Nymphaea hybrid cultivar 'Joey Tomocik'",
        "Liriodendron tulipifera",
        "Eucommia ulmoides",
        "Pontederia crassipes",
        "Selenicereus monacanthus",
        "Glycine max",
        "Capsicum annuum cultivar Jeju",
    ]
    df = pd.read_csv(SPECIES_LIST)
    targets = {s.lower().strip() for s in ([args.species] if args.species else DEFAULT_TARGET_SPECIES)}
    species_srrs: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        species = str(row["species"]).strip()
        if species.lower() not in targets:
            continue
        srr_field = str(row.get("sra", "")).strip()
        if not srr_field or srr_field.lower() in ("nan", "none", ""):
            continue
        srrs = [s.strip() for s in srr_field.replace(";", ",").split(",") if s.strip()]
        species_srrs[species] = srrs

    all_reports = []
    for species in species_srrs:
        species_safe = species.replace(" ", "_").replace(".", "").replace("'", "")
        bam_files = sorted(BAM_DIR.glob(f"{species_safe}_*.sorted.bam"))
        junc_files = sorted(JUNC_DIR.glob(f"{species_safe}_*.junctions.bed"))

        if not bam_files:
            logger.warning(f"No BAM files found for {species}, skipping validation")
            continue

        logger.info(f"Validating {species} with {len(bam_files)} BAM(s) ...")
        report = validate_species(species, bam_files, junc_files)
        all_reports.append(report)

    # Write JSON report
    json_out = OUTPUT_DIR / "validation_report.json"
    json_out.write_text(json.dumps(all_reports, indent=2))

    # Write Markdown summary
    md_lines = ["# RNA-seq Boundary Validation Report\n\n"]
    for r in all_reports:
        species = r["species"]
        md_lines.append(f"## {species}\n\n")
        md_lines.append(f"Genes evaluated: {r['genes_evaluated']}\n\n")

        verdict_counts = defaultdict(int)
        for gene_res in r["results"]:
            verdict_counts[gene_res["verdict"]] += 1

        md_lines.append("| Verdict | Count |\n|---------|-------|\n")
        for v, c in sorted(verdict_counts.items()):
            md_lines.append(f"| {v} | {c} |\n")
        md_lines.append("\n")

        # Detail strong calls
        for gene_res in r["results"]:
            if gene_res["verdict"] in ("strong_support_mitoflow", "strong_support_ncbi", "strand_mismatch"):
                md_lines.append(f"**{gene_res['gene']}**: {gene_res['verdict']}\n")
                for detail in gene_res.get("details", []):
                    md_lines.append(f"- {detail}\n")
                md_lines.append("\n")

    md_out = OUTPUT_DIR / "validation_report.md"
    md_out.write_text("".join(md_lines))

    logger.info(f"Report written to {md_out} and {json_out}")

    # Print summary
    total_genes = sum(r["genes_evaluated"] for r in all_reports)
    total_mitoflow = sum(
        1 for r in all_reports for g in r["results"] if g["verdict"] == "strong_support_mitoflow"
    )
    total_ncbi = sum(
        1 for r in all_reports for g in r["results"] if g["verdict"] == "strong_support_ncbi"
    )
    total_ambiguous = sum(
        1 for r in all_reports for g in r["results"] if g["verdict"] == "ambiguous"
    )

    logger.info("=" * 40)
    logger.info(f"Total genes evaluated: {total_genes}")
    logger.info(f"Strong support MitoFlow: {total_mitoflow}")
    logger.info(f"Strong support NCBI: {total_ncbi}")
    logger.info(f"Ambiguous / no evidence: {total_ambiguous}")


if __name__ == "__main__":
    main()
