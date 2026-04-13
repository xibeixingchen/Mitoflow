"""Protein-coding gene annotation using pyhmmer.

Core annotation strategy:
  1. Six-frame translation of input genome
  2. pyhmmer hmmsearch against HMM profile database
  3. Gene boundary refinement (start/stop codons)
  4. Special gene handling (RNA editing, non-standard starts)
  5. BLAST fallback for divergent genes
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pyhmmer
from pyhmmer import easel, plan7
from Bio.Seq import Seq

from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation, ExonRecord, Strand
from ..db.manager import DBManager
from .trans_splicing import annotate_trans_spliced_genes

logger = logging.getLogger(__name__)


# Core genes that must be detected - force BLASTn search if HMM fails
CORE_GENES_FORCE_BLAST = [
    "atp1", "atp4", "atp6", "atp8", "atp9",
    "cob", "cox1", "cox2", "cox3",
    "nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9",
]


@dataclass
class HMMHit:
    """Raw HMM search hit before boundary refinement."""
    gene_name: str
    start: int        # 1-based in genome
    end: int          # inclusive
    strand: int       # +1 or -1
    score: float
    evalue: float
    domain_score: float
    ali_start: int    # alignment start on target
    ali_end: int      # alignment end on target


@dataclass
class PCGConfig:
    """Configuration for PCG annotation."""
    evalue: float = 1e-5
    min_score: float = 30.0  # 降低阈值以检测更多基因（原值50）
    min_gene_length_aa: int = 30     # ~90 bp minimum
    max_gene_length_aa: int = 2500
    start_codon_search_range: int = 250  # search upstream for start codon
    stop_codon_search_range: int = 250   # search downstream for stop codon
    transl_table: int = 1              # Standard genetic code (NOT Table 2)
    threads: int = 4


# Standard genetic code (Table 1) codon table
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

START_CODONS = {"ATG"}  # Standard start codon; ACG allowed for RNA editing genes
STOP_CODONS = {"TAA", "TAG", "TGA"}
STOP_GAIN_CODONS = {"CAA", "CAG", "CGA", "TGG"}  # RNA editing: C->U creates stop
MAX_CONSERVATIVE_SLIDE = 10  # Maximum adjustment in conservative refinement (bp)

# Expected gene lengths with ±10% tolerance for validation
# Based on plant mitochondrial gene lengths (approximate bp)
# min/max: reasonable range across species for filtering candidates
# reject_below/reject_above: ±10% from midpoint, reject genes outside this range
EXPECTED_LENGTHS_WITH_TOLERANCE = {
    # Expected lengths with ±10% reject thresholds (based on midpoint of min/max)
    "atp1": {"min": 1400, "max": 1600, "reject_below": 1350, "reject_above": 1650},
    "atp4": {"min": 500, "max": 650, "reject_below": 517, "reject_above": 632},
    "atp6": {"min": 900, "max": 1200, "reject_below": 945, "reject_above": 1155},
    "atp8": {"min": 400, "max": 550, "reject_below": 427, "reject_above": 522},
    "atp9": {"min": 200, "max": 280, "reject_below": 216, "reject_above": 264},
    "cob": {"min": 1100, "max": 1300, "reject_below": 1080, "reject_above": 1320},
    "cox1": {"min": 1500, "max": 1650, "reject_below": 1417, "reject_above": 1732},
    "cox2": {"min": 700, "max": 900, "reject_below": 720, "reject_above": 880},
    "cox3": {"min": 750, "max": 900, "reject_below": 742, "reject_above": 907},
    "nad1": {"min": 900, "max": 1100, "reject_below": 900, "reject_above": 1100},
    "nad2": {"min": 1100, "max": 1400, "reject_below": 1125, "reject_above": 1375},
    "nad3": {"min": 300, "max": 400, "reject_below": 315, "reject_above": 385},
    "nad4": {"min": 1300, "max": 1600, "reject_below": 1305, "reject_above": 1595},
    "nad4L": {"min": 250, "max": 350, "reject_below": 270, "reject_above": 330},
    "nad5": {"min": 1800, "max": 2300, "reject_below": 1845, "reject_above": 2255},
    "nad6": {"min": 550, "max": 700, "reject_below": 562, "reject_above": 687},
    "nad7": {"min": 1100, "max": 1400, "reject_below": 1125, "reject_above": 1375},
    "nad9": {"min": 500, "max": 650, "reject_below": 517, "reject_above": 632},
}


def translate_codon(codon: str) -> str:
    """Translate a single codon using standard genetic code (Table 1)."""
    codon = codon.upper()
    if len(codon) != 3:
        return "X"
    if "N" in codon:
        return "X"
    return CODON_TABLE.get(codon, "X")


def translate_sequence(nt_seq: str, table: int = 1, stop_at_stop: bool = False) -> str:
    """Translate nucleotide sequence to protein (standard code).
    
    Args:
        nt_seq: Nucleotide sequence
        table: Genetic code table (default: 1 for standard code)
        stop_at_stop: If True, stop at first stop codon; if False, translate full sequence
    """
    protein = []
    for i in range(0, len(nt_seq) - 2, 3):
        codon = nt_seq[i:i+3]
        aa = translate_codon(codon)
        if aa == "*" and stop_at_stop:
            break
        protein.append(aa)
    return "".join(protein)


def six_frame_translation(sequence: str) -> list[tuple[str, int]]:
    """Generate six-frame translations of a DNA sequence.

    Returns list of (protein_sequence, frame_offset) where:
    - Frame +1, +2, +3: forward strand
    - Frame -1, -2, -3: reverse complement
    """
    comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")
    rc = sequence.translate(comp)[::-1]

    frames = []
    for frame in range(3):
        prot = translate_sequence(sequence[frame:], stop_at_stop=False)
        frames.append((prot, frame + 1))  # frames 1, 2, 3

    for frame in range(3):
        prot = translate_sequence(rc[frame:], stop_at_stop=False)
        frames.append((prot, -(frame + 1)))  # frames -1, -2, -3

    return frames


def _validate_hit_length(hit: HMMHit) -> bool:
    """Validate hit length against expected range.

    Returns True if hit is within acceptable range.
    Returns False if hit is significantly over-extended or fragmented.

    This validation prevents genes from being annotated with lengths
    significantly deviating from their expected values. For example,
    atp4 (expected ~579bp) should not be annotated as 599bp+.

    Args:
        hit: HMMHit object to validate

    Returns:
        True if valid, False if should be rejected
    """
    # Trans-spliced genes have scattered exons - skip length validation
    # They will be validated after merging
    TRANS_SPLICED_SKIP_VALIDATION = {"nad1", "nad2", "nad5", "nad4", "nad7", "cox2", "rpl2", "rps3", "ccmFC"}
    if hit.gene_name.lower() in {g.lower() for g in TRANS_SPLICED_SKIP_VALIDATION}:
        return True  # Skip validation for trans-spliced genes

    if hit.gene_name not in EXPECTED_LENGTHS_WITH_TOLERANCE:
        return True

    expected = EXPECTED_LENGTHS_WITH_TOLERANCE[hit.gene_name]
    hit_len = hit.end - hit.start + 1

    # Reject if over-extended (common case)
    if hit_len > expected["reject_above"]:
        logger.warning(
            f"{hit.gene_name}: {hit_len}bp exceeds reject threshold "
            f"{expected['reject_above']}bp - over-extended"
        )
        return False

    # Reject if too short (fragmented)
    if hit_len < expected["reject_below"]:
        logger.warning(
            f"{hit.gene_name}: {hit_len}bp below reject threshold "
            f"{expected['reject_below']}bp - fragmented"
        )
        return False

    return True


def _validate_gene_span(gene_name: str, start: int, end: int) -> bool:
    """Validate gene span is reasonable, exclude pseudogenes.

    Args:
        gene_name: Gene name (lowercase)
        start: Gene start
        end: Gene end

    Returns:
        True if span is reasonable
    """
    span = abs(end - start)

    # Max allowed spans for trans-spliced genes (already merged)
    # Increased to accommodate large genomes (e.g., Cucumis ~1.5Mb)
    max_spans = {
        "nad1": 1500000,
        "nad2": 500000,
        "nad5": 2000000,
        "nad4": 500000,
        "nad7": 500000,
        "cox2": 200000,
        "rpl2": 200000,
        "rps3": 500000,
    }

    # Regular genes shouldn't exceed 50kb
    max_allowed = max_spans.get(gene_name.lower(), 50000)

    if span > max_allowed:
        logger.warning(f"{gene_name}: span {span}bp exceeds max {max_allowed}, skipping")
        return False

    return True


def annotate_pcg(
    genome: GenomeSequence,
    db_manager: DBManager,
    config: PCGConfig | None = None,
) -> list[GeneAnnotation]:
    """Annotate protein-coding genes in a mitochondrial genome.

    Args:
        genome: Loaded genome sequence
        db_manager: Database manager with HMM profiles
        config: Annotation parameters

    Returns:
        List of GeneAnnotation objects
    """
    if config is None:
        config = PCGConfig()

    # Step 1: Search with HMM profiles
    raw_hits = _search_hmm(genome, db_manager, config)
    logger.info(f"HMM search found {len(raw_hits)} raw hits")

    # Step 1b: BLASTn fallback for genes not found by HMM
    # PMGA uses direct BLASTn for smallExonGenes; we apply it as fallback
    found_genes = set()
    for hit in raw_hits:
        found_genes.add(db_manager.resolve_gene_name(hit.gene_name))

    blast_hits = _blastn_fallback(genome, db_manager, found_genes, config)
    if blast_hits:
        logger.info(f"BLASTn fallback found {len(blast_hits)} additional hits")
        raw_hits.extend(blast_hits)

    if not raw_hits:
        logger.warning("No HMM hits found. Check database or input quality.")
        return []

    # Step 2: Refine boundaries using reference-based approach
    refined_hits = _refine_boundaries_reference(raw_hits, genome, db_manager, config)
    logger.debug(f"Boundary refinement: {len(refined_hits)} hits retained, showing rpl16:")
    for h in refined_hits:
        if h.gene_name.lower() == 'rpl16':
            logger.debug(f"  refined rpl16 hit: {h.start}-{h.end} strand={h.strand}")
    logger.info(f"Boundary refinement: {len(refined_hits)} hits retained")

    # Step 2b: Validate lengths against expected (±10% tolerance)
    valid_hits = [h for h in refined_hits if _validate_hit_length(h)]
    if len(valid_hits) < len(refined_hits):
        filtered_count = len(refined_hits) - len(valid_hits)
        logger.info(f"Length validation: filtered {filtered_count} hits outside ±10% tolerance")
    refined_hits = valid_hits
    logger.debug(f"After length validation, rpl16 hits:")
    for h in refined_hits:
        if h.gene_name.lower() == 'rpl16':
            logger.debug(f"  validated rpl16 hit: {h.start}-{h.end} strand={h.strand}")

    # Step 3: Resolve overlaps
    final_hits = _resolve_overlaps(refined_hits)
    logger.info(f"After overlap resolution: {len(final_hits)} genes")
    logger.debug(f"After overlap resolution, rpl16 hits:")
    for h in final_hits:
        if h.gene_name.lower() == 'rpl16':
            logger.debug(f"  final rpl16 hit: {h.start}-{h.end} strand={h.strand}")

    # Step 4: Convert to GeneAnnotation objects
    annotations = []
    for hit in final_hits:
        gene_name = db_manager.resolve_gene_name(hit.gene_name)
        product = db_manager.get_product(gene_name)

        # Validate gene span to exclude false positives/pseudogenes
        if not _validate_gene_span(gene_name, hit.start, hit.end):
            continue

        strand = Strand.PLUS if hit.strand == 1 else Strand.MINUS

        gene = GeneAnnotation(
            gene_name=gene_name,
            product=product,
            exons=[ExonRecord(start=hit.start, end=hit.end, strand=strand)],
            strand=strand,
            transl_table=config.transl_table,
            source_method="HMM",
            confidence=hit.score / 500.0 if hit.score > 0 else 0.0,
            score=hit.score,
            evalue=hit.evalue,
        )
        annotations.append(gene)

    # Step 5: Merge same-gene annotations into multi-exon genes
    annotations = _merge_same_gene_annotations(annotations, db_manager)
    logger.info(f"After merging same-gene annotations: {len(annotations)} genes")

    # Step 5b: Search for missing core genes using BLASTn
    found_genes = {a.gene_name.lower() for a in annotations}
    missing_core = [g for g in CORE_GENES_FORCE_BLAST if g.lower() not in found_genes]
    if missing_core:
        logger.info(f"Missing core genes: {missing_core}. Forcing BLASTn search...")
        blast_hits = _search_missing_core_genes_blast(genome, db_manager, missing_core, config)
        for hit in blast_hits:
            gene_name = db_manager.resolve_gene_name(hit.gene_name)
            product = db_manager.get_product(gene_name)

            # Validate gene span to exclude false positives/pseudogenes
            if not _validate_gene_span(gene_name, hit.start, hit.end):
                continue

            strand = Strand.PLUS if hit.strand == 1 else Strand.MINUS
            gene = GeneAnnotation(
                gene_name=gene_name,
                product=product,
                exons=[ExonRecord(start=hit.start, end=hit.end, strand=strand)],
                strand=strand,
                transl_table=config.transl_table,
                source_method="BLASTn",
                confidence=hit.score / 500.0 if hit.score > 0 else 0.0,
                score=hit.score,
                evalue=hit.evalue,
            )
            annotations.append(gene)
        logger.info(f"After BLASTn search for missing genes: {len(annotations)} genes")

    # Step 6: Final filter - remove genes with total exon length < 90bp (30aa)
    min_bp = config.min_gene_length_aa * 3
    filtered = [a for a in annotations if a.total_exon_length >= min_bp]
    if len(filtered) < len(annotations):
        removed = len(annotations) - len(filtered)
        logger.info(f"Removed {removed} genes with total exon length < {min_bp}bp")

    # Step 7: Process trans-spliced genes - merge exons and refine boundaries
    # Convert list to dict for trans-spliced gene processing
    ann_dict: dict[str, GeneAnnotation] = {}
    for ann in filtered:
        # Handle multiple copies of same gene (e.g., trnN.2, trnN.3)
        key = ann.gene_name
        if key in ann_dict:
            # If gene already exists, use the one with longer total exon length
            if ann.total_exon_length > ann_dict[key].total_exon_length:
                ann_dict[key] = ann
        else:
            ann_dict[key] = ann

    # Process trans-spliced genes
    ann_dict = annotate_trans_spliced_genes(genome, db_manager, ann_dict)

    # Convert back to list
    filtered = list(ann_dict.values())
    logger.info(f"After trans-spliced gene processing: {len(filtered)} genes")

    return filtered


def _search_hmm(
    genome: GenomeSequence,
    db_manager: DBManager,
    config: PCGConfig,
) -> list[HMMHit]:
    """Search genome against HMM profile database using pyhmmer."""
    alphabet = easel.Alphabet.amino()

    # Load HMM database
    hmms = []
    hmm_path = db_manager.combined_hmm
    if hmm_path.exists():
        with pyhmmer.plan7.HMMFile(str(hmm_path)) as hmm_file:
            for hmm in hmm_file:
                hmms.append(hmm)
    else:
        # Load individual HMM files
        hmm_files = sorted(db_manager.hmm_dir.glob("*.hmm"))
        if not hmm_files:
            raise FileNotFoundError(
                f"No HMM profiles found in {db_manager.hmm_dir}. "
                "Run 'mitoflow db build' first."
            )
        for hf in hmm_files:
            try:
                with pyhmmer.plan7.HMMFile(str(hf)) as hf_open:
                    for hmm in hf_open:
                        hmms.append(hmm)
            except Exception as e:
                logger.debug(f"Failed to load {hf}: {e}")

    if not hmms:
        logger.warning("No HMMs loaded from database")
        return []

    # Generate six-frame translation
    frames = six_frame_translation(genome.sequence)

    # Process each frame - split long sequences into chunks
    MAX_SEQ_LEN = 50000  # Maximum sequence length per chunk (amino acids)
    hits = []
    
    for prot_seq, frame_offset in frames:
        if not prot_seq or len(prot_seq) < 30:
            continue
        
        # Split long sequences into chunks to avoid pyhmmer limits
        seq_chunks = []
        chunk_starts = []
        for i in range(0, len(prot_seq), MAX_SEQ_LEN):
            chunk = prot_seq[i:i + MAX_SEQ_LEN]
            if len(chunk) >= 30:  # Minimum length for meaningful search
                seq_chunks.append(chunk)
                chunk_starts.append(i)
        
        # Search each chunk
        for chunk_idx, (chunk_seq, chunk_start) in enumerate(zip(seq_chunks, chunk_starts)):
            # Create digital sequence - replace * (stop) with X (unknown)
            # pyhmmer's amino alphabet does not include *, but accepts X
            safe_seq = chunk_seq.replace("*", "X")
            text_seq = easel.TextSequence(
                name=f"frame_{frame_offset}_chunk{chunk_idx}".encode(),
                sequence=safe_seq,
            )
            digital_seq = text_seq.digitize(alphabet)
            seq_block = easel.DigitalSequenceBlock(alphabet, [digital_seq])

            # Search - iterate over each HMM
            pipeline = plan7.Pipeline(alphabet, Z=len(hmms))
            for hmm in hmms:
                try:
                    top_hits = pipeline.search_hmm(hmm, seq_block)
                    for hit in top_hits:
                        if hit.included:
                            for domain in hit.domains:
                                # Adjust coordinates for chunk offset
                                adjusted_ali_from = domain.alignment.target_from + chunk_start
                                adjusted_ali_to = domain.alignment.target_to + chunk_start
                                
                                # Convert protein coordinates back to genome coordinates
                                genome_start, genome_end, strand = _protein_to_genome_coords(
                                    adjusted_ali_from, adjusted_ali_to,
                                    frame_offset, len(genome.sequence),
                                )
                                if genome_start is None:
                                    continue

                                gene_name = hmm.name.decode() if isinstance(hmm.name, bytes) else str(hmm.name)

                                # Apply score and length filters
                                hit_length_nt = genome_end - genome_start + 1
                                hit_length_aa = hit_length_nt // 3

                                # Use HMM model length as expected gene length
                                hmm_len_aa = hmm.M  # model length in amino acids
                                expected_bp = hmm_len_aa * 3
                                # Reject if hit is >1.5x expected gene length
                                if hit_length_nt > expected_bp * 1.5 and expected_bp > 90:
                                    logger.info(f"  [Filtered] {gene_name}: {hit_length_nt}bp > 1.5x{expected_bp}bp (score={hit.score:.1f})")
                                    continue
                                if hit.score < config.min_score:
                                    logger.info(f"  [Filtered] {gene_name}: score {hit.score:.1f} < {config.min_score} (len={hit_length_nt}bp)")
                                    continue
                                if hit_length_aa < config.min_gene_length_aa:
                                    logger.info(f"  [Filtered] {gene_name}: {hit_length_aa}aa < {config.min_gene_length_aa}aa min (score={hit.score:.1f})")
                                    continue
                                if hit_length_aa > config.max_gene_length_aa:
                                    logger.info(f"  [Filtered] {gene_name}: {hit_length_aa}aa > {config.max_gene_length_aa}aa max (score={hit.score:.1f})")
                                    continue

                                # Log accepted hits
                                logger.info(f"  [Accepted] {gene_name}: {hit_length_nt}bp, score={hit.score:.1f}, strand={strand}")

                                hits.append(HMMHit(
                                    gene_name=gene_name,
                                    start=genome_start,
                                    end=genome_end,
                                    strand=strand,
                                    score=hit.score,
                                    evalue=hit.evalue,
                                    domain_score=domain.score,
                                    ali_start=adjusted_ali_from,
                                    ali_end=adjusted_ali_to,
                                ))
                except Exception as e:
                    logger.debug(f"Error searching HMM {hmm.name} on frame {frame_offset} chunk {chunk_idx}: {e}")
                    continue

    return hits


def _blastn_fallback(
    genome: GenomeSequence,
    db_manager: DBManager,
    found_genes: set[str],
    config: PCGConfig,
) -> list[HMMHit]:
    """BLAST fallback for genes missed by HMM.

    PMGA uses direct BLASTn for small exon genes. We use tblastn
    (protein vs nucleotide) since we have protein references.
    This catches sdh4, nad4L and other small/divergent genes.
    """
    tblastn = shutil.which("tblastn")
    makeblastdb = shutil.which("makeblastdb")
    if not tblastn or not makeblastdb:
        return []

    # Genes that benefit from BLAST fallback
    BLAST_FALLBACK_GENES = {
        "sdh4", "sdh3", "nad4L", "rps19", "rps12", "rps14",
        "ccmC", "nad9", "rpl16", "rps4", "rps7", "atp4",
    }

    hits = []
    ref_dir = db_manager.blast_ref_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build BLAST db from genome
        genome_fa = Path(tmpdir) / "genome.fasta"
        with open(genome_fa, "w") as f:
            f.write(f">{genome.seqid}\n{genome.sequence}\n")

        db_path = Path(tmpdir) / "genome_db"
        try:
            subprocess.run(
                [makeblastdb, "-in", str(genome_fa), "-dbtype", "nucl", "-out", str(db_path)],
                capture_output=True, text=True, timeout=120, check=True,
            )
        except Exception:
            return []

        for gene_name in BLAST_FALLBACK_GENES:
            if gene_name in found_genes:
                continue

            resolved = db_manager.resolve_gene_name(gene_name)
            if resolved in found_genes:
                continue

            ref_file = ref_dir / f"{gene_name}.Protein.fasta"
            if not ref_file.exists():
                continue

            out_file = Path(tmpdir) / f"tblastn_{gene_name}.tsv"
            cmd = [
                tblastn,
                "-query", str(ref_file),
                "-db", str(db_path),
                "-out", str(out_file),
                "-outfmt", "6 qseqid sseqid qstart qend sstart send evalue bitscore length pident qcovs",
                "-evalue", "1e-5",
                "-max_target_seqs", "3",
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except Exception:
                continue

            if not out_file.exists():
                continue

            for line in out_file.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 11:
                    continue
                try:
                    sstart = int(parts[4])
                    send = int(parts[5])
                    score = float(parts[7])
                    pident = float(parts[9])
                    qcovs = float(parts[10])
                except (ValueError, IndexError):
                    continue

                if pident < 65 or qcovs < 50:
                    continue

                # Determine strand and coordinates
                if sstart <= send:
                    strand = 1
                    start, end = sstart, send
                else:
                    strand = -1
                    start, end = send, sstart

                hits.append(HMMHit(
                    gene_name=gene_name,
                    start=start, end=end,
                    strand=strand,
                    score=score,
                    evalue=float(parts[6]),
                    domain_score=score,
                    ali_start=int(parts[2]),
                    ali_end=int(parts[3]),
                ))

    return hits


def _search_missing_core_genes_blast(
    genome: GenomeSequence,
    db_manager: DBManager,
    missing_genes: list[str],
    config: PCGConfig,
) -> list[HMMHit]:
    """Force BLASTn search for missing core genes.

    For genes like atp1, cox2, nad1-nad7 that were not detected by HMM,
    use BLASTn against reference CDS database to find them.

    Args:
        genome: Genome sequence
        db_manager: Database manager
        missing_genes: List of gene names to search
        config: PCG configuration

    Returns:
        List of HMMHit objects for found genes
    """
    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")
    if not blastn:
        logger.warning("blastn not available, skipping forced gene search")
        return []

    hits = []
    ref_dir = db_manager.blast_ref_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build BLAST db from genome
        genome_fa = Path(tmpdir) / "genome.fasta"
        genome_fa.write_text(f">{genome.seqid}\n{genome.sequence}\n")

        if makeblastdb:
            subprocess.run(
                [makeblastdb, "-in", str(genome_fa), "-dbtype", "nucl"],
                capture_output=True, timeout=60,
            )

        for gene_name in missing_genes:
            # Try CDS reference file
            ref_file = ref_dir / f"{gene_name}.CDS.fasta"
            if not ref_file.exists():
                # Try protein file as fallback (convert to tblastn)
                ref_file = ref_dir / f"{gene_name}.Protein.fasta"
                if not ref_file.exists():
                    logger.info(f"  No reference file for {gene_name}, skipped")
                    continue

            out_file = Path(tmpdir) / f"{gene_name}_blast.tsv"

            # Use blastn for CDS or tblastn for Protein
            if ref_file.name.endswith(".CDS.fasta"):
                cmd = [
                    blastn,
                    "-query", str(ref_file),
                    "-db", str(genome_fa),
                    "-out", str(out_file),
                    "-outfmt", "6 qseqid sseqid sstart send evalue bitscore pident length",
                    "-evalue", "1e-10",
                    "-max_target_seqs", "3",
                    "-task", "blastn",
                ]
            else:
                # tblastn for protein queries
                tblastn = shutil.which("tblastn")
                if not tblastn:
                    continue
                cmd = [
                    tblastn,
                    "-query", str(ref_file),
                    "-db", str(genome_fa),
                    "-out", str(out_file),
                    "-outfmt", "6 qseqid sseqid qstart qend sstart send evalue bitscore pident qcovs",
                    "-evalue", "1e-5",
                    "-max_target_seqs", "3",
                ]

            try:
                subprocess.run(cmd, capture_output=True, timeout=120)
            except Exception as e:
                logger.warning(f"  BLAST failed for {gene_name}: {e}")
                continue

            if not out_file.exists() or not out_file.read_text().strip():
                logger.info(f"  No BLAST hit for {gene_name}")
                continue

            # Parse best hit
            lines = out_file.read_text().strip().split("\n")
            best_hit = None
            best_score = 0

            for line in lines:
                parts = line.split("\t")
                if len(parts) < 8:
                    continue
                try:
                    if ref_file.name.endswith(".CDS.fasta"):
                        # blastn output: qseqid sseqid sstart send evalue bitscore pident length
                        sstart = int(parts[2])
                        send = int(parts[3])
                        score = float(parts[5])
                        pident = float(parts[6])
                        length = int(parts[7])
                        qcovs = length * 100 / 100  # approximate
                    else:
                        # tblastn output: qseqid sseqid qstart qend sstart send evalue bitscore pident qcovs
                        sstart = int(parts[4])
                        send = int(parts[5])
                        score = float(parts[7])
                        pident = float(parts[8])
                        qcovs = float(parts[9]) if len(parts) > 9 else 50
                except (ValueError, IndexError):
                    continue

                if pident < 70 or qcovs < 50:
                    continue

                if score > best_score:
                    best_score = score
                    best_hit = (sstart, send, score, pident)

            if best_hit:
                sstart, send, score, pident = best_hit
                # Determine strand
                if sstart <= send:
                    strand = 1
                    start, end = sstart, send
                else:
                    strand = -1
                    start, end = send, sstart

                logger.info(f"  [BLAST found] {gene_name}: {start}-{end} ({strand}), score={score:.1f}, pident={pident:.1f}%")

                hits.append(HMMHit(
                    gene_name=gene_name,
                    start=start, end=end,
                    strand=strand,
                    score=score,
                    evalue=1e-10,
                    domain_score=score,
                    ali_start=1,
                    ali_end=end - start + 1,
                ))

    return hits


def _protein_to_genome_coords(
    ali_start: int, ali_end: int,
    frame_offset: int, genome_length: int,
) -> tuple[int | None, int | None, int]:
    """Convert protein alignment coordinates to genome coordinates.

    Args:
        ali_start: Start position in protein (1-based)
        ali_end: End position in protein (1-based)
        frame_offset: Frame (1,2,3 for forward; -1,-2,-3 for reverse)
        genome_length: Total genome length

    Returns:
        (genome_start, genome_end, strand) - 1-based, inclusive
    """
    prot_start = ali_start - 1  # 0-based
    prot_end = ali_end - 1      # 0-based

    nt_start = prot_start * 3   # 0-based nt position in frame
    nt_end = prot_end * 3 + 2   # inclusive

    if frame_offset > 0:
        # Forward strand
        genome_start = nt_start + (frame_offset - 1) + 1  # 1-based
        genome_end = nt_end + (frame_offset - 1) + 1
        return genome_start, genome_end, 1
    else:
        # Reverse strand
        abs_frame = abs(frame_offset)
        rc_start = nt_start + (abs_frame - 1)
        rc_end = nt_end + (abs_frame - 1)
        # Convert RC coords to forward coords
        genome_end = genome_length - rc_start
        genome_start = genome_length - rc_end
        return genome_start, genome_end, -1


def _refine_boundaries(
    hits: list[HMMHit],
    genome: GenomeSequence,
    db_manager: DBManager,
    config: PCGConfig,
) -> list[HMMHit]:
    """Refine gene boundaries to start/stop codons.

    Follows PMGA logic (03.CDSCheck.py start_edit/stop_edit):
    - Start from the HMM hit boundary, slide OUTWARD in steps of 3bp
    - Forward strand: start slides left (-3), stop slides right (+3)
    - Reverse strand: start slides right (+3) on genome, reading RC codons;
                      stop slides left (-3) on genome, reading RC codons
    - Search extent is limited to max(config.range, hit_length*0.5)
      to prevent runaway expansion.
    """
    comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")
    refined = []
    for hit in hits:
        gene_name = hit.gene_name
        is_stop_gain = db_manager.is_stop_gain_gene(gene_name)
        is_start_gain = db_manager.is_start_gain_gene(gene_name)

        start = hit.start
        end = hit.end
        hit_len = end - start + 1
        new_start = start
        new_end = end

        allowed_starts = START_CODONS | ({"ACG"} if is_start_gain else set())
        if gene_name == "mttB":
            allowed_starts |= {"ATA", "GTG"}
        elif gene_name == "rpl16":
            allowed_starts |= {"GTG"}

        # Dynamic search extent: use configured range but cap at 0.5x hit length
        start_extent = min(config.start_codon_search_range, max(150, hit_len // 2))
        stop_extent = min(config.stop_codon_search_range, max(150, hit_len // 2))

        if hit.strand == 1:
            # === Forward strand start: slide left from hit.start ===
            new_s = start - 3
            slid = 0
            while slid <= start_extent and new_s >= 1:
                codon = genome.sequence[new_s - 1:new_s - 1 + 3].upper()
                if codon in allowed_starts:
                    new_start = new_s
                    break
                if codon in STOP_CODONS:
                    break
                new_s -= 3
                slid += 3

            # === Forward strand stop: slide right from hit.end ===
            new_e = end + 3
            slid = 0
            while slid <= stop_extent and new_e + 2 <= genome.length:
                codon = genome.sequence[new_e - 1:new_e - 1 + 3].upper()
                if codon in STOP_CODONS:
                    new_end = new_e + 2
                    break
                if is_stop_gain and codon in STOP_GAIN_CODONS:
                    new_end = new_e + 2
                    break
                new_e += 3
                slid += 3

        else:
            # === Reverse strand: start at HIGH coord, slide right ===
            new_s = end + 3
            slid = 0
            while slid <= start_extent and new_s <= genome.length:
                codon_fwd = genome.sequence[new_s - 3:new_s].upper()
                codon = codon_fwd.translate(comp)[::-1]
                if codon in allowed_starts:
                    new_end = new_s
                    break
                if codon in STOP_CODONS:
                    break
                new_s += 3
                slid += 3

            # Stop at LOW coord, slide left
            new_e = start - 3
            slid = 0
            while slid <= stop_extent and new_e >= 1:
                codon_fwd = genome.sequence[new_e - 1:new_e - 1 + 3].upper()
                codon = codon_fwd.translate(comp)[::-1]
                if codon in STOP_CODONS:
                    new_start = new_e
                    break
                if is_stop_gain and codon in STOP_GAIN_CODONS:
                    new_start = new_e
                    break
                new_e -= 3
                slid += 3

        # Validate: refined gene shouldn't be >2x original HMM hit length
        refined_len = new_end - new_start + 1
        if refined_len > hit_len * 2.5 and hit_len > 100:
            # Boundary search went too far; keep original
            new_start = start
            new_end = end

        if new_start != start or new_end != end:
            hit = HMMHit(
                gene_name=hit.gene_name, start=new_start, end=new_end,
                strand=hit.strand, score=hit.score, evalue=hit.evalue,
                domain_score=hit.domain_score,
                ali_start=hit.ali_start, ali_end=hit.ali_end,
            )

        refined.append(hit)

    return refined


def _refine_boundaries_reference(
    hits: list[HMMHit],
    genome: GenomeSequence,
    db_manager: DBManager,
    config: PCGConfig,
) -> list[HMMHit]:
    """Refine boundaries using reference sequence BLAST (PMGA-style approach).

    Instead of sliding outward from HMM hit, use blastn against reference
    CDS database to find exact gene boundaries. This prevents over-extension.

    Strategy:
    1. For each hit, extract region ±100bp around HMM boundary
    2. blastn against reference CDS for this specific gene
    3. Use best BLAST hit coordinates as refined boundary
    4. Only use conservative sliding search as fallback if BLAST fails

    Args:
        hits: Raw HMM hits to refine
        genome: Genome sequence
        db_manager: Database manager with reference files
        config: PCG configuration

    Returns:
        Refined HMMHit objects with corrected boundaries
    """
    tblastn = shutil.which("tblastn")
    makeblastdb = shutil.which("makeblastdb")
    if not tblastn or not makeblastdb:
        # Fallback to conservative refinement
        logger.warning("tblastn/makeblastdb not found, using conservative refinement")
        return [_refine_single_conservative(hit, genome, db_manager, config)
                for hit in hits]

    refined = []
    ref_dir = db_manager.blast_ref_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build BLAST db from genome
        genome_fa = Path(tmpdir) / "genome.fasta"
        genome_fa.write_text(f">{genome.seqid}\n{genome.sequence}\n")

        db_path = Path(tmpdir) / "genome_db"
        try:
            subprocess.run(
                [makeblastdb, "-in", str(genome_fa), "-dbtype", "nucl",
                 "-out", str(db_path)],
                capture_output=True, text=True, timeout=60, check=True,
            )
        except subprocess.SubprocessError as e:
            logger.warning(f"makeblastdb failed: {e.stderr}")
            return [_refine_single_conservative(hit, genome, db_manager, config)
                    for hit in hits]

        for hit in hits:
            gene_name = hit.gene_name
            # Use Protein.fasta for tblastn (we have protein references)
            ref_file = ref_dir / f"{gene_name}.Protein.fasta"

            if not ref_file.exists():
                # No reference available, use conservative refinement
                logger.debug(f"No Protein reference for {gene_name}, using conservative refinement")
                refined.append(_refine_single_conservative(hit, genome, db_manager, config))
                continue

            # Run tblastn: query=reference Protein, subject=genome (translated)
            out_file = Path(tmpdir) / f"tblastn_{gene_name}.tsv"
            cmd = [
                tblastn,
                "-query", str(ref_file),
                "-db", str(db_path),
                "-out", str(out_file),
                "-outfmt", "6 qseqid sseqid sstart send evalue bitscore pident length sframe",
                "-evalue", "1e-10",
                "-max_target_seqs", "5",
            ]

            try:
                # Run tblastn - output goes to file specified by -out parameter
                # Do NOT capture output, let it write to the file
                subprocess.run(cmd, check=True, timeout=120)
            except subprocess.SubprocessError:
                refined.append(_refine_single_conservative(hit, genome, db_manager, config))
                continue

            # Parse tblastn results to find best hit near the HMM region
            best_hit = _parse_tblastn_for_boundary(out_file, hit, genome)

            # Debug: check if tblastn file was created and has content
            if not out_file.exists():
                logger.warning(f"tblastn output file not created for {gene_name}")
            elif not out_file.read_text().strip():
                logger.warning(f"tblastn output file empty for {gene_name}")
            else:
                logger.debug(f"tblastn found hits for {gene_name} near HMM {hit.start}-{hit.end}")

            if best_hit:
                logger.info(f"tblastn refined {gene_name}: {hit.start}-{hit.end} -> {best_hit.start}-{best_hit.end}")
                refined.append(best_hit)
            else:
                # BLAST failed or no good hit, use conservative refinement
                logger.debug(f"tblastn no hit for {gene_name}, using conservative refinement")
                refined.append(_refine_single_conservative(hit, genome, db_manager, config))

    return refined


def _parse_tblastn_for_boundary(
    blast_file: Path,
    hmm_hit: HMMHit,
    genome: GenomeSequence,
) -> HMMHit | None:
    """Parse tblastn results to extract refined boundary.

    tblastn returns protein hits on translated genome.
    Frame indicates strand: +1/+2/+3 = plus, -1/-2/-3 = minus

    After finding tblastn hit, extend upstream to find start codon
    since reference proteins may be truncated.

    Args:
        blast_file: Path to tblastn output file
        hmm_hit: Original HMM hit
        genome: Genome sequence

    Returns:
        Refined HMMHit or None if no suitable hit found
    """
    if not blast_file.exists():
        logger.warning(f"tblastn file does not exist: {blast_file}")
        return None

    content = blast_file.read_text().strip()
    if not content:
        logger.warning(f"tblastn file is empty: {blast_file}")
        return None

    START_CODONS = ["ATG"]
    STOP_CODONS = ["TAA", "TAG", "TGA"]
    comp = str.maketrans("ATGC", "TACG")

    best_hits = []
    line_count = 0
    filtered_count = 0

    with open(blast_file) as f:
        for line in f:
            line_count += 1
            parts = line.strip().split("\t")
            if len(parts) < 9:
                continue

            try:
                qseqid = parts[0]
                sstart = int(parts[2])
                send = int(parts[3])
                evalue = float(parts[4])
                bitscore = float(parts[5])
                pident = float(parts[6])
                length = int(parts[7])  # Protein alignment length (aa)
                frame = int(parts[8])

                # Determine strand from frame
                strand = Strand.PLUS if frame > 0 else Strand.MINUS

                # tblastn returns genome coords (sstart/send)
                # These are 1-based coordinates on the genome
                genome_start = min(sstart, send)
                genome_end = max(sstart, send)

                # Score hit by proximity to HMM hit and identity
                hmm_start = hmm_hit.start
                hmm_end = hmm_hit.end

                # Check if hit is near HMM region (within 200bp)
                if genome_end < hmm_start - 200 or genome_start > hmm_end + 200:
                    filtered_count += 1
                    logger.debug(f"Filtered tblastn hit for {hmm_hit.gene_name}: too far from HMM")
                    continue  # Too far from HMM hit

                # Score = bitscore + proximity bonus + identity bonus
                proximity = min(abs(genome_start - hmm_start), abs(genome_end - hmm_end))
                score = bitscore + (500 - proximity) + pident
                logger.debug(f"Accepted tblastn hit for {hmm_hit.gene_name}: score={score:.1f}")

                best_hits.append((genome_start, genome_end, strand, score, pident, frame))
            except (ValueError, IndexError) as e:
                logger.debug(f"Parse error: {e}")
                continue

    logger.debug(f"tblastn parsed {line_count} lines, found {len(best_hits)} hits for {hmm_hit.gene_name}")

    if not best_hits:
        return None

    # Sort by score, take best
    best_hits.sort(key=lambda x: -x[3])
    best_start, best_end, best_strand, _, pident, frame = best_hits[0]

    # Extend to find start codon
    # Reference proteins may be truncated OR extended relative to actual gene
    # Need to search BOTH upstream (left) and downstream (right) for ATG
    gene_name = hmm_hit.gene_name.lower()

    # For genes with known issues
    genes_need_extension = {"rpl16", "rps1", "atp6", "ccmfc", "ccmfn", "rpl2"}
    extension_range = 300 if gene_name in genes_need_extension else 150

    new_start = best_start
    new_end = best_end

    START_CODONS_EXT = ["ATG", "GTG"]  # Include GTG for some genes
    STOP_CODONS = ["TAA", "TAG", "TGA"]

    if best_strand == Strand.PLUS:
        # Search downstream (right) first - reference may be longer than gene
        search_pos = best_start
        searched = 0
        while searched <= extension_range and search_pos <= genome.length - 2:
            codon = genome.sequence[search_pos - 1:search_pos - 1 + 3].upper()
            if codon in START_CODONS_EXT:
                new_start = search_pos
                logger.debug(f"tblastn found start codon {codon} downstream at {search_pos}")
                break
            if codon in STOP_CODONS:
                break
            search_pos += 3
            searched += 3

        # If no ATG found downstream, search upstream (left)
        if new_start == best_start:
            search_pos = best_start - 3
            searched = 0
            while searched <= extension_range and search_pos >= 1:
                codon = genome.sequence[search_pos - 1:search_pos - 1 + 3].upper()
                if codon in START_CODONS_EXT:
                    new_start = search_pos
                    logger.debug(f"tblastn found start codon {codon} upstream at {search_pos}")
                    break
                if codon in STOP_CODONS:
                    break
                search_pos -= 3
                searched += 3
        logger.debug(f"ATG search for {hmm_hit.gene_name}: downstream {searched}bp, start={new_start}")
    else:
        # For minus strand, start codon is at HIGH coordinate
        # Search upstream (left) first - reference may be longer
        search_pos = best_end
        searched = 0
        while searched <= extension_range and search_pos >= 3:
            # Get codon and reverse complement
            codon_fwd = genome.sequence[search_pos - 3:search_pos].upper()
            codon = codon_fwd.translate(comp)[::-1]
            if codon in START_CODONS_EXT:
                new_end = search_pos
                logger.debug(f"tblastn found start codon {codon} upstream at {search_pos} (minus)")
                break
            if codon in STOP_CODONS:
                break
            search_pos -= 3
            searched += 3

        # If not found, search downstream (right)
        if new_end == best_end:
            search_pos = best_end + 3
            searched = 0
            while searched <= extension_range and search_pos <= genome.length:
                codon_fwd = genome.sequence[search_pos - 3:search_pos].upper()
                codon = codon_fwd.translate(comp)[::-1]
                if codon in START_CODONS_EXT:
                    new_end = search_pos
                    logger.debug(f"tblastn found start codon {codon} downstream at {search_pos} (minus)")
                    break
                if codon in STOP_CODONS:
                    break
                search_pos += 3
                searched += 3

    # Create refined HMMHit with extended boundaries
    logger.debug(
        f"tblastn refined {hmm_hit.gene_name}: "
        f"{hmm_hit.start}-{hmm_hit.end} → {new_start}-{new_end} "
        f"(extended from tblastn hit {best_start}-{best_end})"
    )

    return HMMHit(
        gene_name=hmm_hit.gene_name,
        start=new_start,
        end=new_end,
        strand=best_strand,
        score=hmm_hit.score,
        evalue=hmm_hit.evalue,
        domain_score=hmm_hit.domain_score,
        ali_start=hmm_hit.ali_start,
        ali_end=hmm_hit.ali_end,
    )


def _parse_blastn_for_boundary(
    blast_file: Path,
    hmm_hit: HMMHit,
    genome: GenomeSequence,
) -> HMMHit | None:
    """Parse blastn results to extract refined boundary (DEPRECATED - use tblastn version).

    Find the BLAST hit that best matches the HMM region and use its
    coordinates as refined boundaries.

    Args:
        blast_file: Path to blastn output file
        hmm_hit: Original HMM hit
        genome: Genome sequence

    Returns:
        Refined HMMHit or None if no suitable hit found
    """
    if not blast_file.exists() or not blast_file.read_text().strip():
        return None

    lines = blast_file.read_text().strip().split("\n")
    if not lines:
        return None

    # Find the best hit near the HMM region
    hmm_center = (hmm_hit.start + hmm_hit.end) // 2
    hmm_len = hmm_hit.end - hmm_hit.start + 1

    best_hit = None
    best_score = -1

    for line in lines:
        parts = line.split("\t")
        # blastn outfmt: qseqid sseqid sstart send evalue bitscore pident length
        if len(parts) < 8:
            continue

        try:
            sstart = int(parts[2])
            send = int(parts[3])
            evalue = float(parts[4])
            score = float(parts[5])
            pident = float(parts[6])
            length = int(parts[7])
        except (ValueError, IndexError):
            continue

        # Filter by quality (pident threshold for nucleotide alignment)
        if pident < 70:
            continue

        # Determine strand and coordinates
        if sstart <= send:
            strand = 1
            blast_start, blast_end = sstart, send
        else:
            strand = -1
            blast_start, blast_end = send, sstart

        # Check if this hit is near the HMM region
        blast_center = (blast_start + blast_end) // 2
        dist = abs(blast_center - hmm_center)

        # Prefer hits that are:
        # 1. Close to HMM region (within 2x HMM length)
        # 2. High score
        # 3. Strand matches HMM
        if strand == hmm_hit.strand and dist < hmm_len * 2:
            # Combined score: BLAST score adjusted by proximity
            combined = score * (1 - dist / (hmm_len * 4))
            if combined > best_score:
                best_score = combined
                best_hit = (blast_start, blast_end, strand, score)

    if best_hit:
        new_start, new_end, new_strand, new_score = best_hit
        return HMMHit(
            gene_name=hmm_hit.gene_name,
            start=new_start,
            end=new_end,
            strand=new_strand,
            score=max(new_score, hmm_hit.score),
            evalue=hmm_hit.evalue,
            domain_score=hmm_hit.domain_score,
            ali_start=hmm_hit.ali_start,
            ali_end=hmm_hit.ali_end,
        )

    return None


def _refine_single_conservative(
    hit: HMMHit,
    genome: GenomeSequence,
    db_manager: DBManager,
    config: PCGConfig,
) -> HMMHit:
    """Conservative boundary refinement - only adjust ±10bp max.

    This is a fallback when reference-based refinement is not available.
    It only makes small adjustments to find start/stop codons very close
    to the HMM boundary, preventing over-extension.

    Strategy:
    - For start: scan upstream (lower coord) for start codon
    - For stop: scan both upstream and downstream within ±10bp
    - If stop codon found upstream (HMM over-extended), use that
    - If stop codon found downstream (HMM truncated), use that

    Args:
        hit: Single HMM hit to refine
        genome: Genome sequence
        db_manager: Database manager for gene metadata
        config: PCG configuration

    Returns:
        Refined HMMHit with conservative adjustments
    """
    comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")
    gene_name = hit.gene_name
    is_stop_gain = db_manager.is_stop_gain_gene(gene_name)
    is_start_gain = db_manager.is_start_gain_gene(gene_name)

    start = hit.start
    end = hit.end
    new_start = start
    new_end = end

    allowed_starts = START_CODONS | ({"ACG"} if is_start_gain else set())
    if gene_name == "mttB":
        allowed_starts |= {"ATA", "GTG"}
    elif gene_name == "rpl16":
        allowed_starts |= {"GTG"}

    if hit.strand == 1:
        # Forward strand

        # Check for start codon upstream (within MAX_CONSERVATIVE_SLIDE)
        # Scan backward from HMM start toward lower coordinates
        for offset in range(0, MAX_CONSERVATIVE_SLIDE + 1, 3):
            pos = start - offset
            if pos >= 1:
                codon = genome.sequence[pos - 1:pos + 2].upper()
                if codon in allowed_starts:
                    new_start = pos
                    break

        # For stop codon, scan BOTH directions within ±MAX_CONSERVATIVE_SLIDE
        # First priority: stop codon upstream (if HMM over-extended)
        found_stop_upstream = False
        for offset in range(0, MAX_CONSERVATIVE_SLIDE + 1, 3):
            # Check positions ending at end-offset (scanning backward)
            pos = end - offset - 2  # Position of stop codon start
            if pos >= 1 and pos + 2 <= end:
                codon = genome.sequence[pos - 1:pos + 2].upper()
                if codon in STOP_CODONS:
                    new_end = pos + 2  # Include stop codon
                    found_stop_upstream = True
                    break
                if is_stop_gain and codon in STOP_GAIN_CODONS:
                    new_end = pos + 2
                    found_stop_upstream = True
                    break

        # If no upstream stop found, check downstream
        if not found_stop_upstream:
            for offset in range(0, MAX_CONSERVATIVE_SLIDE + 1, 3):
                pos = end + offset  # Position after end
                if pos + 2 <= genome.length:
                    codon = genome.sequence[pos - 1:pos + 2].upper()
                    if codon in STOP_CODONS:
                        new_end = pos + 2
                        break
                    if is_stop_gain and codon in STOP_GAIN_CODONS:
                        new_end = pos + 2
                        break

    else:
        # Reverse strand
        # On reverse strand: start is at high coord, stop is at low coord

        # Check for start codon downstream (higher coord, within MAX_CONSERVATIVE_SLIDE)
        for offset in range(0, MAX_CONSERVATIVE_SLIDE + 1, 3):
            pos = end + offset
            if pos <= genome.length:
                # Get forward strand codon, then reverse complement
                codon_fwd = genome.sequence[pos - 3:pos].upper()
                codon = codon_fwd.translate(comp)[::-1]
                if codon in allowed_starts:
                    new_end = pos
                    break

        # For stop codon on reverse strand, scan both directions
        # Stop is at low coordinate end
        found_stop_upstream = False

        # First check if stop is beyond the HMM hit (need to scan toward higher coords)
        for offset in range(0, MAX_CONSERVATIVE_SLIDE + 1, 3):
            pos = start + offset  # Higher coordinate
            if pos + 2 <= genome.length:
                codon_fwd = genome.sequence[pos - 1:pos + 2].upper()
                codon = codon_fwd.translate(comp)[::-1]
                if codon in STOP_CODONS:
                    new_start = pos
                    found_stop_upstream = True
                    break
                if is_stop_gain and codon in STOP_GAIN_CODONS:
                    new_start = pos
                    found_stop_upstream = True
                    break

        # If not found, check toward lower coords
        if not found_stop_upstream:
            for offset in range(0, MAX_CONSERVATIVE_SLIDE + 1, 3):
                pos = start - offset
                if pos >= 1:
                    codon_fwd = genome.sequence[pos - 1:pos + 2].upper()
                    codon = codon_fwd.translate(comp)[::-1]
                    if codon in STOP_CODONS:
                        new_start = pos
                        break
                    if is_stop_gain and codon in STOP_GAIN_CODONS:
                        new_start = pos
                        break

    # Only update if we found valid codons
    if new_start != start or new_end != end:
        return HMMHit(
            gene_name=hit.gene_name,
            start=new_start,
            end=new_end,
            strand=hit.strand,
            score=hit.score,
            evalue=hit.evalue,
            domain_score=hit.domain_score,
            ali_start=hit.ali_start,
            ali_end=hit.ali_end,
        )

    return hit


def _merge_same_gene_annotations(
    annotations: list[GeneAnnotation],
    db_manager: DBManager,
) -> list[GeneAnnotation]:
    """Merge multiple annotations for the same gene into multi-exon genes.

    In plant mitochondria, many genes are trans-spliced (exons scattered
    across the genome): nad1/nad2/nad5 have 5 exons each, nad4/nad7 have
    4 exons, cox2/rpl2/rps3/ccmFC have 2 exons. The HMM search finds
    each exon as a separate annotation; this function merges them.
    
    CRITICAL: Must use reasonable max_gap limits to prevent merging
    unrelated hits that happen to have the same gene name.
    """
    if not annotations:
        return []

    # Genes with widely-separated exons in plant mitochondria.
    # Trans-spliced: exons can be >100kb apart, but we need an upper limit
    # to prevent merging unrelated fragmented hits.
    # Based on Arabidopsis reference: nad5 max span ~340kb
    TRANS_SPLICING_GENES = {
        "nad1": 200000,  # ~176kb span in Arabidopsis
        "nad2": 100000,  # ~71kb span in Arabidopsis
        "nad5": 350000,  # ~333kb span in Arabidopsis
        "nad4": 50000,   # ~8kb span, but allow generous buffer
        "nad7": 30000,   # ~6kb span, but allow generous buffer
    }
    # Multi-exon genes with moderate inter-exon gaps
    MULTIEXON_GENES = {
        "rpl2": 20000,   # ~1-2kb typical
        "rps3": 20000,
        "ccmFC": 20000,
        "cox2": 20000,
    }

    # Group by gene name
    groups: dict[str, list[GeneAnnotation]] = {}
    for ann in annotations:
        groups.setdefault(ann.gene_name, []).append(ann)

    merged = []
    for gene_name, gene_anns in groups.items():
        if len(gene_anns) == 1:
            merged.append(gene_anns[0])
            continue

        # Sort by genomic start
        gene_anns.sort(key=lambda a: a.genomic_start)

        # Check if all on same strand
        strands = set(a.strand for a in gene_anns)
        if len(strands) > 1:
            # Different strands — different gene copies, keep separate
            merged.extend(gene_anns)
            continue

        strand = gene_anns[0].strand
        
        # Get appropriate max_gap for this gene
        if gene_name in TRANS_SPLICING_GENES:
            max_gap = TRANS_SPLICING_GENES[gene_name]
        elif gene_name in MULTIEXON_GENES:
            max_gap = MULTIEXON_GENES[gene_name]
        else:
            # Conservative default for unknown multi-exon genes
            max_gap = 5000

        # Cluster by proximity
        clusters = [gene_anns[:1]]
        for ann in gene_anns[1:]:
            prev = clusters[-1][-1]
            gap = ann.genomic_start - prev.genomic_end - 1

            if 0 < gap <= max_gap:
                clusters[-1].append(ann)
            else:
                clusters.append([ann])

        # Each cluster -> one GeneAnnotation with multiple exons
        for cluster in clusters:
            if len(cluster) == 1:
                merged.append(cluster[0])
            else:
                # Collect all exons from all annotations in this cluster
                all_exons = []
                for ann in cluster:
                    all_exons.extend(ann.exons)

                # Sort exons by position
                if strand == Strand.PLUS:
                    all_exons.sort(key=lambda e: e.start)
                else:
                    all_exons.sort(key=lambda e: e.start, reverse=True)

                # Re-number exons
                numbered_exons = []
                for i, exon in enumerate(all_exons, 1):
                    numbered_exons.append(ExonRecord(
                        start=exon.start, end=exon.end,
                        strand=strand, number=i,
                    ))

                # Use the best-scoring annotation as base
                best = max(cluster, key=lambda a: a.score)
                merged.append(GeneAnnotation(
                    gene_name=gene_name,
                    product=best.product,
                    exons=numbered_exons,
                    strand=strand,
                    notes=best.notes,
                    exceptions=best.exceptions,
                    transl_table=best.transl_table,
                    source_method="HMM-merged",
                    confidence=best.confidence,
                    score=best.score,
                    evalue=best.evalue,
                ))

    return sorted(merged, key=lambda a: a.genomic_start)


def _resolve_overlaps(hits: list[HMMHit]) -> list[HMMHit]:
    """Resolve overlapping gene annotations.

    For same-gene overlaps: merge into one hit spanning both.
    For different-gene overlaps: keep higher scored hit.
    """
    if not hits:
        return []
    
    # Known expected lengths for genes (approximate, in bp)
    EXPECTED_LENGTHS = {
        "atp1": 1524, "atp4": 579, "atp6": 1050, "atp8": 477, "atp9": 225,
        "ccmB": 621, "ccmC": 771, "ccmFC": 2289, "ccmFC1": 500, "ccmFC2": 600,
        "ccmFN": 600, "ccmFN1": 1149, "ccmFN2": 612,
        "cob": 1182, "cox1": 1584, "cox2": 783, "cox3": 798,
        "matR": 1971, "mttB": 828,
        "nad1": 978, "nad2": 1467, "nad3": 357, "nad4": 1488, "nad4L": 303,
        "nad5": 2010, "nad6": 618, "nad7": 1185, "nad9": 573,
        "rpl2": 1050, "rpl5": 558, "rpl10": 495, "rpl16": 516,
        "rps1": 999, "rps3": 1671, "rps4": 1089, "rps7": 447,
        "rps10": 321, "rps12": 378, "rps13": 531, "rps14": 315, "rps19": 279,
        "sdh3": 414, "sdh4": 465,
    }
    
    # Related gene groups that should be merged
    RELATED_GROUPS = [
        {"ccmFC", "ccmFC1", "ccmFC2"},
        {"ccmFN", "ccmFN1", "ccmFN2"},
        {"ccmB", "ccmB1", "ccmB2"},
        {"atp6", "atp6b"},
        {"nad4", "nad4L"},
        {"rps3", "rps3a", "rps3b"},
    ]
    
    def get_related_group(name: str) -> set[str]:
        for group in RELATED_GROUPS:
            if name in group:
                return group
        return {name}
    
    def get_length_score(hit: HMMHit) -> float:
        """Score based on how close hit length is to expected length."""
        if hit.gene_name in EXPECTED_LENGTHS:
            expected = EXPECTED_LENGTHS[hit.gene_name]
        else:
            return 1.0
        actual = hit.end - hit.start + 1
        ratio = min(actual, expected) / max(actual, expected)
        return ratio
    
    def combined_score(hit: HMMHit) -> float:
        """Combined score: HMM score * length合理性."""
        return hit.score * get_length_score(hit)
    
    def hits_overlap(h1: HMMHit, h2: HMMHit, min_overlap_ratio: float = 0.3) -> bool:
        """Check if two hits overlap significantly."""
        if h1.strand != h2.strand:
            return False
        o_start = max(h1.start, h2.start)
        o_end = min(h1.end, h2.end)
        if o_end < o_start:
            return False  # No overlap
        overlap_len = o_end - o_start + 1
        min_len = min(h1.end - h1.start, h2.end - h2.start) + 1
        return min_len > 0 and overlap_len / min_len > min_overlap_ratio
    
    def should_merge(h1: HMMHit, h2: HMMHit) -> bool:
        """Check if two hits should be merged (same/related gene + overlap)."""
        # Must be same strand
        if h1.strand != h2.strand:
            return False
        # Must be same gene or related genes
        if h1.gene_name != h2.gene_name:
            # Check if they are related
            if h2.gene_name not in get_related_group(h1.gene_name):
                return False
        # Must overlap or be adjacent (within 50bp)
        o_start = max(h1.start, h2.start)
        o_end = min(h1.end, h2.end)
        gap = max(0, o_start - o_end - 1) if o_end < o_start else 0
        return o_end >= o_start or gap <= 50
    
    def merge_two_hits(h1: HMMHit, h2: HMMHit) -> HMMHit:
        """Merge two hits into one."""
        best = h1 if combined_score(h1) >= combined_score(h2) else h2
        # Use the base name if genes are related
        names = {h1.gene_name, h2.gene_name}
        if names in RELATED_GROUPS or any(names <= g for g in RELATED_GROUPS):
            # Use the shortest name as the base
            gene_name = min(names, key=len)
        else:
            gene_name = h1.gene_name
        return HMMHit(
            gene_name=gene_name,
            start=min(h1.start, h2.start),
            end=max(h1.end, h2.end),
            strand=h1.strand,
            score=max(h1.score, h2.score),
            evalue=min(h1.evalue, h2.evalue),
            domain_score=max(h1.domain_score, h2.domain_score),
            ali_start=min(h1.ali_start, h2.ali_start),
            ali_end=max(h1.ali_end, h2.ali_end),
        )

    # Phase 1: Group hits by (strand, gene_name) and merge within groups
    from collections import defaultdict
    
    # Group by strand and base gene name
    hit_groups = defaultdict(list)
    for hit in hits:
        group_key = (hit.strand, hit.gene_name)
        hit_groups[group_key].append(hit)
    
    # Also check for related genes and group them
    merged_hits = []
    processed = set()
    
    for (strand, gene_name), group in hit_groups.items():
        if (strand, gene_name) in processed:
            continue
        
        # Find all related genes
        related = get_related_group(gene_name)
        all_hits = list(group)
        processed.add((strand, gene_name))
        
        for other_name in related:
            if other_name != gene_name:
                key = (strand, other_name)
                if key in hit_groups:
                    all_hits.extend(hit_groups[key])
                    processed.add(key)
        
        # Sort by position
        all_hits.sort(key=lambda h: (h.start, h.end))
        
        # Merge overlapping/adjacent hits
        if not all_hits:
            continue
            
        current = all_hits[0]
        for hit in all_hits[1:]:
            if should_merge(current, hit):
                current = merge_two_hits(current, hit)
            else:
                merged_hits.append(current)
                current = hit
        merged_hits.append(current)

    # Phase 2: Resolve cross-gene overlaps
    # Sort by combined score (highest first)
    merged_hits.sort(key=combined_score, reverse=True)
    
    kept = []
    for hit in merged_hits:
        # Check for significant overlap with already kept hits
        conflicts = False
        for existing in kept:
            if hit.gene_name == existing.gene_name:
                continue
            # Allow overlap between related genes
            if hit.gene_name in get_related_group(existing.gene_name):
                continue
            if hits_overlap(hit, existing):
                conflicts = True
                break
        if not conflicts:
            kept.append(hit)

    return sorted(kept, key=lambda h: h.start)
