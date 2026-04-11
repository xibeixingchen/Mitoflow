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
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pyhmmer
from pyhmmer import easel, plan7
from Bio.Seq import Seq

from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation, ExonRecord, Strand
from ..db.manager import DBManager

logger = logging.getLogger(__name__)


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
    min_score: float = 50.0
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

    # Step 2: Refine boundaries
    refined_hits = _refine_boundaries(raw_hits, genome, db_manager, config)
    logger.info(f"Boundary refinement: {len(refined_hits)} hits retained")

    # Step 3: Resolve overlaps
    final_hits = _resolve_overlaps(refined_hits)
    logger.info(f"After overlap resolution: {len(final_hits)} genes")

    # Step 4: Convert to GeneAnnotation objects
    annotations = []
    for hit in final_hits:
        gene_name = db_manager.resolve_gene_name(hit.gene_name)
        product = db_manager.get_product(gene_name)

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

    # Step 6: Final filter - remove genes with total exon length < 90bp (30aa)
    min_bp = config.min_gene_length_aa * 3
    filtered = [a for a in annotations if a.total_exon_length >= min_bp]
    if len(filtered) < len(annotations):
        removed = len(annotations) - len(filtered)
        logger.info(f"Removed {removed} genes with total exon length < {min_bp}bp")
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
                                    logger.debug(f"  {gene_name}: {hit_length_nt}bp > 1.5x{expected_bp}bp, skipped")
                                    continue
                                if hit.score < config.min_score:
                                    logger.debug(f"  {gene_name}: score {hit.score:.1f} < {config.min_score}, skipped")
                                    continue
                                if hit_length_aa < config.min_gene_length_aa:
                                    logger.debug(f"  {gene_name}: {hit_length_aa}aa < {config.min_gene_length_aa}aa min, skipped")
                                    continue
                                if hit_length_aa > config.max_gene_length_aa:
                                    logger.debug(f"  {gene_name}: {hit_length_aa}aa > {config.max_gene_length_aa}aa max, skipped")
                                    continue

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
    import shutil
    import subprocess

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
