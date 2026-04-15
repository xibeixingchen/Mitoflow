"""CMS (Cytoplasmic Male Sterility) candidate gene prediction.

Pipeline:
1. Scan all ORFs (ATG-initiated, ≥300bp, Table 1)
2. Subtract known annotated genes (≥80% overlap)
3. Chimera detection (BLAST vs mitochondrial gene DB)
4. Transmembrane domain prediction
5. Known CMS gene homology search
6. Genomic context analysis (near atp/cox/nad/repeats)
7. Multi-dimensional scoring + ranking
8. Visualization + report
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Known CMS genes database (49+ genes from 17+ species) ────────
# Updated: 2024-2025 with latest NCBI publications
# Sources: PubMed, GenBank, Plant Cell, Mol Plant, PNAS

KNOWN_CMS_GENES = [
    # (gene_name, species, cms_type, length_aa, chimera_sources, evidence_level)
    # Rice (Oryza sativa) - 9 genes
    ("orf79", "rice", "BT-CMS", 79, "cox1+unknown", "gold"),
    ("orfH79", "rice", "HL-CMS", 79, "cox1+unknown", "strong"),
    ("WA352", "rice", "WA-CMS", 352, "rpl5+orf284+orf288", "gold"),
    ("orf312", "rice", "Tadukan-CMS", 312, "COX11 domain", "gold"),
    ("orf182", "rice", "D1-CMS", 182, "sorghum mt homolog", "strong"),
    ("orf307", "rice", "CW-CMS", 307, "unknown", "medium"),
    ("orf314", "rice", "T65-CMS", 314, "cox2+unknown", "gold"),  # 2024 Mito-TALEN
    ("orf113", "rice", "RT98A-CMS", 113, "chimeric", "medium"),
    ("orf352", "rice", "RT102-CMS", 352, "WA352 variant", "gold"),  # 2023 validated
    
    # Maize (Zea mays) - 5 genes
    ("T-urf13", "maize", "T-CMS", 115, "atp6+rrn26+unknown", "classic"),
    ("orf355", "maize", "S-CMS", 355, "unknown", "medium"),
    ("orf77", "maize", "S-CMS", 77, "unknown", "medium"),
    ("atp6c", "maize", "C-CMS", 230, "atp6 variant", "gold"),  # 2022 Yang et al.
    ("orf279", "maize", "T-CMS", 279, "atp8-related", "strong"),
    
    # Wheat (Triticum) - 2 genes
    ("orf279_wheat", "wheat", "T-CMS", 279, "atp8 chimera", "gold"),  # 2021 Hao et al.
    ("orf256", "wheat", "T-CMS", 256, "cox1 fragment", "medium"),
    
    # Rapeseed (Brassica napus) - 4 genes
    ("orf224", "rapeseed", "Pol-CMS", 224, "atp8+rps3+unknown", "strong"),
    ("orf222", "rapeseed", "Nap-CMS", 222, "atp8+unknown", "strong"),
    ("orf263", "rapeseed", "Tour-CMS", 263, "near atp6", "medium"),
    ("orf346", "rapeseed", "Nsa-CMS", 346, "cox1+unknown", "gold"),  # 2021 Sang et al.
    
    # Radish (Raphanus sativus) - 5 genes
    ("orf138", "radish", "Ogu-CMS", 138, "non-chimeric", "gold"),
    ("orf125", "radish", "Kos-CMS", 125, "orf138 variant", "gold"),
    ("orf463", "radish", "Don-CMS", 463, "cox1+unknown", "medium"),
    ("orf112", "radish", "Bel-CMS", 112, "orf138 deletion", "gold"),  # 2021
    ("orf463a", "radish", "NWB-CMS", 463, "cox1+unknown", "strong"),  # 2020
    
    # Mustard (Brassica juncea) - 3 genes
    ("orf288", "mustard", "Hau-CMS", 288, "nad5+unknown", "strong"),
    ("orf288_hau", "mustard", "Hau-CMS", 288, "nad3+atp9-like", "gold"),  # 2014 validated
    ("orf108", "mustard", "Moricandia-CMS", 108, "M.arvensis", "medium"),
    
    # Cabbage (Brassica oleracea) - 5 genes (C5-CMS system)
    ("orf222a", "cabbage", "C5-CMS", 222, "atp8 N-terminal", "gold"),  # 2022
    ("orf188a", "cabbage", "C5-CMS", 188, "atp6-like", "medium"),
    ("orf261a", "cabbage", "C5-CMS", 261, "cox1 related", "medium"),
    ("orf286a", "cabbage", "C5-CMS", 286, "unknown", "medium"),
    ("orf322a", "cabbage", "C5-CMS", 322, "atp9 cotranscript", "medium"),
    
    # Sunflower (Helianthus annuus) - 3 genes
    ("orf522", "sunflower", "PET1-CMS", 522, "atpA cotranscript", "strong"),
    ("orf228", "sunflower", "PET2-CMS", 228, "atp9 chimera", "strong"),
    ("orf558", "sunflower", "ANN2-CMS", 558, "cox2 chimera", "medium"),
    
    # Petunia - 1 gene
    ("pcf", "petunia", "CMS", 402, "atp9+cox2 fusion", "strong"),
    
    # Sorghum - 1 gene
    ("orf107", "sorghum", "A3-CMS", 107, "atp6+urf209", "medium"),
    
    # Pepper - 1 gene
    ("orf507", "pepper", "Peterson-CMS", 507, "atp6+coxII+unknown", "strong"),
    
    # Sugarbeet (Beta vulgaris) - 3 genes
    ("preSatp6", "sugarbeet", "Owen-CMS", 300, "atp6 leader", "medium"),
    ("orf129", "sugarbeet", "E-CMS", 129, "unknown", "medium"),
    ("Gcox1-ext", "sugarbeet", "G-CMS", 0, "cox1 extension", "medium"),
    
    # Onion (Allium cepa) - 2 genes
    ("orf725", "onion", "CMS-T", 725, "chimeric", "medium"),
    ("orf219", "onion", "CMS-T-specific", 219, "atp1+orfA501", "medium"),
    
    # Pigeonpea - 1 gene
    ("orf147", "pigeonpea", "A4-CMS", 147, "chimeric", "medium"),
    
    # Soybean (Glycine max) - 2 genes (2022)
    ("ORF178", "soybean", "CMS-ZD", 178, "novel chimera", "medium"),
    ("ORF103c", "soybean", "CMS-SX", 103, "novel chimera", "medium"),
    
    # Cotton (Gossypium hirsutum) - 2 genes
    ("orf116b", "cotton", "CMS-D2", 116, "repeat-mediated", "gold"),  # 2024 validated
    ("orf610a", "cotton", "CMS-D2", 610, "repeat-mediated", "medium"),
]

# Standard mitochondrial genes used for chimera detection
MITO_GENE_NAMES = {
    "nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9",
    "cob", "cox1", "cox2", "cox3",
    "atp1", "atp4", "atp6", "atp8", "atp9",
    "ccmB", "ccmC", "ccmFC", "ccmFN",
    "rpl2", "rpl5", "rpl10", "rpl16",
    "rps1", "rps2", "rps3", "rps4", "rps7",
    "rps10", "rps12", "rps13", "rps14", "rps19",
    "matR", "mttB", "sdh3", "sdh4",
    "rrn5", "rrn18", "rrn26",
}

# Genes whose proximity boosts CMS score
PROXIMAL_BOOST_GENES = {"atp1", "atp4", "atp6", "atp8", "atp9",
                        "cox1", "cox2", "cox3", "cob"}


@dataclass
class ChimeraInfo:
    """Chimera (chimeric ORF) analysis result."""
    source_genes: list = field(default_factory=list)  # contributing parent genes
    coverage_by_source: dict = field(default_factory=dict)  # gene -> coverage fraction
    n_sources: int = 0
    chimera_score: float = 0.0


@dataclass
class TMDomain:
    """Transmembrane domain."""
    start: int   # amino acid position
    end: int
    score: float = 0.0


@dataclass
class CMSCandidate:
    """A CMS candidate ORF with scoring."""
    orf_id: str
    start: int       # 1-based genome position
    end: int
    strand: int       # +1 or -1
    length_bp: int = 0
    length_aa: int = 0
    protein_seq: str = ""
    nt_seq: str = ""

    # Analysis results
    chimera: Optional[ChimeraInfo] = None
    tm_domains: list = field(default_factory=list)  # TMDomain
    cms_homolog: str = ""     # known CMS gene hit name
    cms_identity: float = 0.0
    nearby_genes: list = field(default_factory=list)  # genes within 5kb
    near_repeat: bool = False

    # Scoring (0-100)
    chimera_score: float = 0.0
    tm_score: float = 0.0
    homolog_score: float = 0.0
    context_score: float = 0.0
    length_score: float = 0.0
    total_score: float = 0.0
    confidence: str = "Low"  # "High" | "Medium" | "Low"
    ml_confidence: float = 0.0
    feature_vector: dict = field(default_factory=dict)

    @property
    def n_tm_domains(self) -> int:
        return len(self.tm_domains)


@dataclass
class CMSResult:
    """Complete CMS prediction result."""
    candidates: list = field(default_factory=list)  # CMSCandidate, sorted by score
    total_orfs_scanned: int = 0
    orfs_after_filter: int = 0
    n_candidates: int = 0
    high_confidence: int = 0
    medium_confidence: int = 0
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== CMS Candidate Gene Prediction ===",
            f"ORFs scanned: {self.total_orfs_scanned}",
            f"ORFs after filter: {self.orfs_after_filter}",
            f"CMS candidates: {self.n_candidates}",
            f"  High confidence (>=70): {self.high_confidence}",
            f"  Medium confidence (50-70): {self.medium_confidence}",
        ]
        for c in self.candidates[:20]:
            chimera_info = ""
            if c.chimera and c.chimera.source_genes:
                chimera_info = f", chimera={'+'.join(c.chimera.source_genes[:3])}"
            lines.append(
                f"  {c.orf_id}: score={c.total_score:.1f} ({c.confidence}), "
                f"{c.length_aa}aa, {c.n_tm_domains}TM"
                f"{chimera_info}"
            )
        return "\n".join(lines)


def predict_cms(
    fasta_path: Path,
    genome_seq: str,
    annotated_genes: Optional[list] = None,
    gene_protein_db: Optional[Path] = None,
    threads: int = 4,
    min_orf_length: int = 300,
    max_candidates: int = 50,
    use_ml_scorer: bool = False,
    ml_scorer_path: Optional[Path] = None,
    use_plm: bool = False,
    plm_model_path: Optional[Path] = None,
) -> CMSResult:
    """Predict CMS candidate genes from mitochondrial genome.

    Args:
        fasta_path: Genome FASTA file.
        genome_seq: Genome sequence string.
        annotated_genes: Already-annotated genes (to exclude).
        gene_protein_db: FASTA of known mitochondrial proteins (for chimera detection).
        threads: Number of threads for BLAST.
        min_orf_length: Minimum ORF length in bp.
        max_candidates: Maximum candidates to report.
        use_ml_scorer: If True, use ML-based scoring when model is available.
        ml_scorer_path: Optional path to trained model directory.
        use_plm: If True, include ESM-2 pLM features when ML scorer is active.
        plm_model_path: Optional local path to ESM-2 model weights.

    Returns:
        CMSResult with ranked candidates.
    """
    result = CMSResult()

    # Optional ML scorer
    ml_scorer = None
    if use_ml_scorer:
        try:
            from .ml.scorer import MLCMSScorer
            from ..features.extractor import CMSFeatureExtractor

            if ml_scorer_path:
                ml_scorer = MLCMSScorer(ml_scorer_path)
            else:
                default_path = Path(__file__).parent / "data" / "cms" / "models"
                if (default_path / "cms_logreg.joblib").exists() or (default_path / "cms_lgbm.joblib").exists():
                    ml_scorer = MLCMSScorer(default_path)
                else:
                    logger.warning("Default ML scorer not found at %s", default_path)

            if ml_scorer is not None:
                ml_scorer.extractor = CMSFeatureExtractor(
                    use_plm=use_plm,
                    plm_model_path=str(plm_model_path) if plm_model_path else None,
                )
        except ImportError as e:
            logger.warning("ML scorer unavailable: %s", e)
        except Exception as e:
            logger.warning("Failed to load ML scorer: %s", e)

    # Step 1: Scan all ORFs
    orfs = _scan_orfs(genome_seq, min_orf_length)
    result.total_orfs_scanned = len(orfs)
    logger.info(f"Found {len(orfs)} ORFs (>= {min_orf_length}bp)")

    # Step 2: Subtract known annotated genes
    annotated_regions = []
    if annotated_genes:
        for ann in annotated_genes:
            annotated_regions.append((ann.genomic_start, ann.genomic_end))

    filtered_orfs = []
    for orf_start, orf_end, strand, seq in orfs:
        overlap = False
        for gs, ge in annotated_regions:
            overlap_start = max(orf_start, gs)
            overlap_end = min(orf_end, ge)
            if overlap_end >= overlap_start:
                overlap_len = overlap_end - overlap_start + 1
                orf_len = orf_end - orf_start + 1
                if overlap_len / orf_len >= 0.8:
                    overlap = True
                    break
        if not overlap:
            filtered_orfs.append((orf_start, orf_end, strand, seq))

    result.orfs_after_filter = len(filtered_orfs)
    logger.info(f"After removing known genes: {len(filtered_orfs)} ORFs")

    if not filtered_orfs:
        result.warnings.append("No novel ORFs found")
        return result

    # Build candidates
    candidates = []
    for idx, (start, end, strand, seq) in enumerate(filtered_orfs):
        protein = _translate(seq)
        if not protein or len(protein) < 50:
            continue

        candidate = CMSCandidate(
            orf_id=f"orf{len(protein)}_{idx + 1}",
            start=start,
            end=end,
            strand=strand,
            length_bp=len(seq),
            length_aa=len(protein),
            protein_seq=protein,
            nt_seq=seq,
        )
        candidates.append(candidate)

    # Step 3: Chimera detection
    if gene_protein_db and gene_protein_db.exists():
        _detect_chimeras(candidates, gene_protein_db, fasta_path, threads)

    # Step 4: Transmembrane prediction
    _predict_transmembrane(candidates)

    # Step 5: CMS homology
    _check_cms_homology(candidates, fasta_path, threads)

    # Step 6: Genomic context
    if annotated_genes:
        _analyze_context(candidates, annotated_genes, genome_seq)

    # Step 7: Score and rank
    for c in candidates:
        _score_candidate(c, annotated_genes, len(genome_seq), ml_scorer)

    # Sort by total_score (heuristic) or ml_confidence when ML scorer active
    sort_key = lambda c: c.ml_confidence if (use_ml_scorer and c.ml_confidence > 0) else c.total_score
    candidates.sort(key=sort_key, reverse=True)
    result.candidates = candidates[:max_candidates]
    result.n_candidates = len(result.candidates)
    result.high_confidence = sum(1 for c in result.candidates if c.confidence == "High")
    result.medium_confidence = sum(1 for c in result.candidates if c.confidence == "Medium")

    return result


# ── ORF Scanning ─────────────────────────────────────────────────

CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def _scan_orfs(seq: str, min_length: int) -> list:
    """Scan all ATG-initiated ORFs on both strands."""
    seq = seq.upper()
    orfs = []

    # Forward strand
    for frame in range(3):
        i = frame
        while i < len(seq) - 2:
            codon = seq[i:i + 3]
            if codon == "ATG":
                # Found start codon — scan for stop
                orf_start = i
                j = i + 3
                while j < len(seq) - 2:
                    c = seq[j:j + 3]
                    if c in ("TAA", "TAG", "TGA"):
                        orf_end = j + 2  # inclusive
                        orf_len = orf_end - orf_start + 1
                        if orf_len >= min_length:
                            orf_seq = seq[orf_start:j + 3]
                            orfs.append((orf_start + 1, orf_end + 1, 1, orf_seq))
                        i = j + 3
                        break
                    j += 3
                else:
                    i = j
                    continue
            else:
                i += 3

    # Reverse strand
    comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")
    rc = seq.translate(comp)[::-1]

    for frame in range(3):
        i = frame
        while i < len(rc) - 2:
            codon = rc[i:i + 3]
            if codon == "ATG":
                orf_start_rc = i
                j = i + 3
                while j < len(rc) - 2:
                    c = rc[j:j + 3]
                    if c in ("TAA", "TAG", "TGA"):
                        orf_len = j + 3 - orf_start_rc
                        if orf_len >= min_length:
                            orf_seq = rc[orf_start_rc:j + 3]
                            # Convert RC coordinates to genome coordinates
                            genome_end = len(seq) - orf_start_rc
                            genome_start = len(seq) - (j + 2)
                            orfs.append((genome_start, genome_end, -1, orf_seq))
                        i = j + 3
                        break
                    j += 3
                else:
                    i = j
                    continue
            else:
                i += 3

    return orfs


def _translate(seq: str) -> str:
    protein = []
    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        aa = CODON_TABLE.get(codon, "X")
        if aa == "*":
            protein.append(aa)
            break
        protein.append(aa)
    return "".join(protein)


# ── Chimera Detection ────────────────────────────────────────────

def _detect_chimeras(
    candidates: list, gene_db: Path, fasta_path: Path, threads: int,
) -> None:
    """Detect chimeric structure by BLASTing ORF proteins against gene DB."""
    blastp = shutil.which("blastp")
    makeblastdb = shutil.which("makeblastdb")
    if not blastp or not makeblastdb:
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Build BLAST db from mitochondrial gene proteins
        db_path = tmp / "gene_db"
        subprocess.run(
            [makeblastdb, "-in", str(gene_db), "-dbtype", "prot",
             "-out", str(db_path)],
            capture_output=True, timeout=120,
        )

        # Write candidate proteins
        query_fa = tmp / "candidates.fasta"
        with open(query_fa, "w") as f:
            for c in candidates:
                f.write(f">{c.orf_id}\n{c.protein_seq}\n")

        # BLAST
        proc = subprocess.run(
            [blastp, "-query", str(query_fa), "-db", str(db_path),
             "-outfmt", "6 qseqid sseqid pident length qcovs evalue bitscore",
             "-evalue", "1e-3", "-max_target_seqs", "10",
             "-num_threads", str(threads)],
            capture_output=True, text=True, timeout=300,
        )

        if proc.returncode != 0:
            return

        # Parse hits per ORF
        orf_hits = defaultdict(list)
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            orf_id = parts[0]
            subject = parts[1].lower().split("_")[0].split(".")[0]
            pident = float(parts[2])
            length = int(parts[3])
            qcov = float(parts[4])

            if pident >= 30 and qcov >= 20:
                orf_hits[orf_id].append({
                    "subject": subject,
                    "pident": pident,
                    "length": length,
                    "qcov": qcov,
                })

        # Analyze chimera structure
        for c in candidates:
            hits = orf_hits.get(c.orf_id, [])
            if not hits:
                continue

            # Group by source gene
            sources = defaultdict(float)
            for h in hits:
                gene = h["subject"]
                if gene in MITO_GENE_NAMES:
                    sources[gene] = max(sources[gene], h["qcov"])

            if len(sources) >= 2:
                c.chimera = ChimeraInfo(
                    source_genes=sorted(sources.keys()),
                    coverage_by_source=dict(sources),
                    n_sources=len(sources),
                    chimera_score=min(1.0, len(sources) * 0.3 + sum(sources.values()) / len(sources) / 100 * 0.5),
                )


# ── Transmembrane Prediction ─────────────────────────────────────

def _predict_transmembrane(candidates: list) -> None:
    """Predict transmembrane domains.

    Uses pytmhmm if available, otherwise a simple hydrophobicity heuristic.
    """
    try:
        import pytmhmm
        has_pytmhmm = True
    except ImportError:
        has_pytmhmm = False

    for c in candidates:
        if has_pytmhmm:
            try:
                # pytmhmm returns TM segments
                from pytmhmm import predict
                tm_pred = predict(c.protein_seq)
                for segment in tm_pred:
                    if hasattr(segment, "start"):
                        c.tm_domains.append(TMDomain(
                            start=segment.start,
                            end=segment.end,
                        ))
            except Exception:
                pass
        else:
            # Simple hydrophobicity-based heuristic
            c.tm_domains = _simple_tm_predict(c.protein_seq)


def _simple_tm_predict(seq: str, window: int = 21, threshold: float = 1.5) -> list:
    """Simple Kyte-Doolittle hydrophobicity TM prediction."""
    kd = {"I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5,
          "M": 1.9, "A": 1.8, "G": -0.4, "T": -0.7, "S": -0.8,
          "W": -0.9, "Y": -1.3, "P": -1.6, "H": -3.2, "E": -3.5,
          "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9, "R": -4.5,
          "X": 0}

    domains = []
    in_domain = False
    start = 0

    for i in range(len(seq) - window + 1):
        segment = seq[i:i + window]
        score = sum(kd.get(aa, 0) for aa in segment) / window
        if score >= threshold and not in_domain:
            start = i + 1
            in_domain = True
        elif score < threshold and in_domain:
            if i - start + 1 >= 15:  # Minimum 15aa for TM
                domains.append(TMDomain(start=start, end=i))
            in_domain = False

    if in_domain and len(seq) - start + 1 >= 15:
        domains.append(TMDomain(start=start, end=len(seq)))

    return domains


# ── CMS Homology ──────────────────────────────────────────────────

def _check_cms_homology(candidates: list, fasta_path: Path, threads: int) -> None:
    """Check candidates against known CMS gene database.

    Requires cms_proteins.fasta to be built first using:
        python -m mitoflow.data.cms.download
    """
    blastp = shutil.which("blastp")
    if not blastp:
        return

    # Try to find CMS reference DB (built by download script)
    cms_db = Path(__file__).parent.parent / "data" / "cms" / "cms_proteins.fasta"
    if not cms_db.exists():
        logger.info(
            "CMS reference DB not found. Build with: "
            "python -m mitoflow.data.cms.download"
        )
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "cms_db"

        subprocess.run(
            ["makeblastdb", "-in", str(cms_db), "-dbtype", "prot",
             "-out", str(db_path)],
            capture_output=True, timeout=60,
        )

        query_fa = tmp / "query.fasta"
        with open(query_fa, "w") as f:
            for c in candidates:
                f.write(f">{c.orf_id}\n{c.protein_seq}\n")

        proc = subprocess.run(
            [blastp, "-query", str(query_fa), "-db", str(db_path),
             "-outfmt", "6 qseqid sseqid pident length evalue bitscore",
             "-evalue", "1e-3", "-max_target_seqs", "1",
             "-num_threads", str(threads)],
            capture_output=True, text=True, timeout=120,
        )

        if proc.returncode != 0:
            return

        hits = {}
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            orf_id = parts[0]
            if orf_id not in hits:
                hits[orf_id] = (parts[1], float(parts[2]))

        for c in candidates:
            if c.orf_id in hits:
                c.cms_homolog, c.cms_identity = hits[c.orf_id]


# ── Genomic Context ──────────────────────────────────────────────

def _analyze_context(candidates: list, annotated_genes: list, genome_seq: str) -> None:
    """Analyze genomic context of candidates."""
    genome_len = len(genome_seq)

    for c in candidates:
        # Find nearby annotated genes (within 5kb)
        nearby = []
        for ann in annotated_genes:
            dist = min(abs(c.start - ann.genomic_end),
                      abs(c.end - ann.genomic_start))
            # Handle circular genome
            dist = min(dist, genome_len - dist)
            if dist <= 5000:
                nearby.append(ann.gene_name.lower())
        c.nearby_genes = nearby

        # Check if near a known CMS-associated gene
        has_proximal = bool(set(nearby) & PROXIMAL_BOOST_GENES)
        c.near_repeat = False  # Would need repeat data


# ── Scoring ──────────────────────────────────────────────────────

def _score_candidate(
    c: CMSCandidate,
    annotated_genes: list | None = None,
    genome_length: int = 0,
    ml_scorer = None,
) -> None:
    """Calculate multi-dimensional CMS score (0-100).

    Weights:
    - Chimera:   0.30
    - TM domain: 0.25
    - CMS homolog: 0.20
    - Context:   0.15
    - Length:    0.10
    """
    # Chimera score
    if c.chimera:
        c.chimera_score = c.chimera.chimera_score * 100
    else:
        c.chimera_score = 5.0  # Small baseline for unknown

    # TM score
    n_tm = c.n_tm_domains
    if n_tm == 0:
        c.tm_score = 10
    elif n_tm <= 2:
        c.tm_score = 60
    elif n_tm <= 4:
        c.tm_score = 100
    elif n_tm <= 6:
        c.tm_score = 80
    else:
        c.tm_score = 50

    # CMS homolog score
    if c.cms_homolog:
        c.homolog_score = 100
    else:
        c.homolog_score = 0

    # Context score
    proximal_boost = any(g in PROXIMAL_BOOST_GENES for g in c.nearby_genes)
    if proximal_boost:
        c.context_score = 80
    elif c.near_repeat:
        c.context_score = 50
    elif c.nearby_genes:
        c.context_score = 30
    else:
        c.context_score = 10

    # Length score (70-500aa optimal)
    if 70 <= c.length_aa <= 500:
        c.length_score = 100
    elif 50 <= c.length_aa < 70:
        c.length_score = 70
    elif 500 < c.length_aa <= 800:
        c.length_score = 60
    else:
        c.length_score = 30

    # Weighted total
    c.total_score = (
        c.chimera_score * 0.30 +
        c.tm_score * 0.25 +
        c.homolog_score * 0.20 +
        c.context_score * 0.15 +
        c.length_score * 0.10
    )

    # Confidence
    if c.total_score >= 70 and c.chimera_score > 30 and c.tm_score > 30:
        c.confidence = "High"
    elif c.total_score >= 50:
        c.confidence = "Medium"
    else:
        c.confidence = "Low"

    # Optional ML confidence
    if ml_scorer is not None and genome_length > 0:
        try:
            c.ml_confidence = ml_scorer.score_candidate(c, annotated_genes, genome_length)
            c.feature_vector = ml_scorer.extractor.extract(c, annotated_genes, genome_length)
        except Exception as e:
            logger.debug("ML scoring failed for %s: %s", c.orf_id, e)
            c.ml_confidence = 0.0


def write_cms_report(
    result: CMSResult,
    output_dir: Path,
    name: str = "MitoFlow",
) -> dict:
    """Write CMS analysis results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    # Text report
    txt_path = output_dir / f"{name}_cms.txt"
    txt_path.write_text(result.summary())
    files["report_txt"] = txt_path

    # TSV table
    tsv_path = output_dir / f"{name}_cms_candidates.tsv"
    with open(tsv_path, "w") as f:
        f.write("orf_id\tstart\tend\tstrand\tlength_aa\ttotal_score\tconfidence\t"
                "chimera_score\ttm_score\thomolog_score\tcontext_score\tlength_score\t"
                "n_tm\tcms_homolog\tchimera_sources\tnearby_genes\n")
        for c in result.candidates:
            sources = ",".join(c.chimera.source_genes) if c.chimera else "-"
            nearby = ",".join(c.nearby_genes) if c.nearby_genes else "-"
            f.write(
                f"{c.orf_id}\t{c.start}\t{c.end}\t{c.strand}\t{c.length_aa}\t"
                f"{c.total_score:.1f}\t{c.confidence}\t"
                f"{c.chimera_score:.1f}\t{c.tm_score:.1f}\t"
                f"{c.homolog_score:.1f}\t{c.context_score:.1f}\t{c.length_score:.1f}\t"
                f"{c.n_tm_domains}\t{c.cms_homolog or '-'}\t{sources}\t{nearby}\n"
            )
    files["candidates_tsv"] = tsv_path

    # Candidate protein FASTA
    fa_path = output_dir / f"{name}_cms_candidates.fasta"
    with open(fa_path, "w") as f:
        for c in result.candidates:
            f.write(f">{c.orf_id} score={c.total_score:.1f} {c.confidence}\n")
            # Write in 80-char lines
            for i in range(0, len(c.protein_seq), 80):
                f.write(c.protein_seq[i:i + 80] + "\n")
    files["candidates_fasta"] = fa_path

    return files
