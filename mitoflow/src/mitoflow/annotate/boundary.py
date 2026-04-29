"""Gene boundary correction.

Translates PMGA v1 logic from 02.editBoundary.py:
- Exon-intron boundary adjustment via sliding window
- Start codon correction (ACG->AUG RNA editing)
- Stop codon correction (CAA->UAA RNA editing for stop-gain genes)
- Short intron removal (<150 bp)
- rpl16 truncation handling
- Multi-exon gene processing
- Fixed offset correction for genes with systematic position errors (Round 2 improvement)
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation, ExonRecord, Strand
from ..db.manager import DBManager
from .pcg import CODON_TABLE, START_CODONS, STOP_CODONS
from .trans_splicing import TRANS_SPLICED_CONFIG

logger = logging.getLogger(__name__)

# ACG is a valid "start" for RNA editing genes (ACG -> AUG after editing)
RNA_EDITING_START = {"ATG", "ACG"}
# Special start codons accepted for specific genes
SPECIAL_STARTS = {
    "mttB": {"ATG", "ATA", "GTG"},
    "rpl16": {"ATG", "GTG"},
    "rps4": {"ATG", "ACG"},  # ACG is probably correct for rps4
}
# Stop-gain RNA editing: C->U editing creates stop codons
STOP_GAIN_CODONS = {"CAA", "CAG", "CGA", "TGG"}
# After editing: CAA->UAA, CAG->UAG, CGA->UGA, TGG->TGA (rare)
SHORT_INTRON_THRESHOLD = 150  # bp, introns shorter than this are removed

# Fixed offset correction for genes with systematic position errors
# Based on Round 1 validation analysis
FIXED_OFFSET_GENES = {
    # cox2: ~1400bp fixed offset (reference boundary definition issue)
    "cox2": {"start_offset": -1400, "end_offset": 0, "reason": "reference_boundary"},
    # rps10: ~900bp offset (RNA editing STGE - start-gain error)
    "rps10": {"start_offset": -900, "end_offset": 0, "reason": "RNA_editing_STGE"},
    # nad7: ~75bp offset (start codon boundary detection)
    "nad7": {"start_offset": -75, "end_offset": 0, "reason": "start_codon_detection"},
    # rps14: ~84bp offset (start codon boundary detection)
    "rps14": {"start_offset": -84, "end_offset": 0, "reason": "start_codon_detection"},
}


def correct_boundaries(
    annotations: list[GeneAnnotation],
    genome: GenomeSequence,
    db_manager: DBManager,
    search_range: int = 30,  # Very conservative: only 30bp adjustment
) -> list[GeneAnnotation]:
    """Apply all boundary corrections to annotations.

    Steps:
    1. Remove short introns (merge exons separated by <150 bp)
    2. Apply fixed offset correction for known systematic errors
    3. Correct start codons (search upstream for ATG/ACG) - CONSERVATIVE
    4. Correct stop codons (search downstream for stop) - CONSERVATIVE
    5. Handle rpl16 truncation
    6. Handle special start codons (mttB ATA, etc.)

    Args:
        annotations: List of gene annotations
        genome: Genome sequence
        db_manager: Database manager for gene metadata
        search_range: How far upstream/downstream to search (bp, default 30)
            Very conservative to prevent over-extension into adjacent genes.
            Only adjust if start/stop codon is very close to HMM boundary.

    Returns:
        Corrected annotations
    """
    corrected = []
    for ann in annotations:
        # Use gene-specific search range if available
        gene_search_range = _get_gene_search_range(ann.gene_name, search_range)

        ann = _remove_short_introns(ann, genome)
        # Phase 3: adaptive tblastn boundary refinement (replaces fixed offsets where possible)
        ann = _refine_boundary_by_tblastn(ann, genome, db_manager)
        # Phase 3: apply fixed offset correction only if tblastn did not refine the boundary
        if ann.source_method != "tblastn":
            ann = _apply_fixed_offset_correction(ann, genome)
        else:
            logger.info(f"Skipping fixed offset for {ann.gene_name} (tblastn refined)")
        # Only do minimal boundary correction - trust HMM hit more
        ann = _correct_start_codon_conservative(ann, genome, db_manager, gene_search_range)
        ann = _correct_stop_codon_conservative(ann, genome, db_manager, gene_search_range)
        ann = _handle_special_genes(ann, genome, db_manager)
        ann = _validate_gene_length(ann, db_manager)
        # Phase 3: restore codon phase continuity across exons after boundary shifts
        ann = _restore_phase_continuity(ann, genome)
        corrected.append(ann)
    return corrected


def _restore_phase_continuity(
    ann: GeneAnnotation, genome: GenomeSequence
) -> GeneAnnotation:
    """Micro-adjust exon boundaries to maintain codon phase across exons.

    After start/stop codon correction, an exon's length may change and break
    the reading frame for subsequent exons. This function attempts ±1 bp or
    ±2 bp shifts of the preceding exon's boundary to restore phase continuity.
    Adjustments are only accepted if they keep the exon ≥3 bp and do not
    overlap the next exon.
    """
    if len(ann.exons) <= 1:
        return ann

    exons = list(ann.exons)
    modified = False

    for i in range(1, len(exons)):
        cumulative_len = sum(e.end - e.start + 1 for e in exons[:i])
        expected_phase = cumulative_len % 3
        actual_phase = exons[i].phase

        if expected_phase == actual_phase:
            continue

        # Determine required length change for previous exon
        delta = (actual_phase - expected_phase) % 3
        if delta == 1:
            shifts = [+1, -2]
        elif delta == 2:
            shifts = [+2, -1]
        else:
            continue

        prev = exons[i - 1]
        nxt = exons[i]

        for shift in shifts:
            if ann.strand == Strand.PLUS:
                new_end = prev.end + shift
                if new_end < prev.start + 2:
                    continue
                if new_end >= nxt.start:
                    continue
                exons[i - 1] = ExonRecord(
                    start=prev.start,
                    end=new_end,
                    strand=prev.strand,
                    number=prev.number,
                    phase=prev.phase,
                )
                modified = True
                break
            else:
                # Minus strand: transcription is high->low coords.
                # To change prev exon length by +shift, move start down.
                new_start = prev.start - shift
                if new_start > prev.end - 2:
                    continue
                if new_start <= nxt.end:
                    continue
                exons[i - 1] = ExonRecord(
                    start=new_start,
                    end=prev.end,
                    strand=prev.strand,
                    number=prev.number,
                    phase=prev.phase,
                )
                modified = True
                break

    if modified:
        notes = list(ann.notes)
        notes.append("phase continuity restored by micro-adjustment")
        return ann.model_copy(update={"exons": exons, "notes": notes})

    return ann.model_copy(update={"exons": exons})


def _refine_boundary_by_tblastn(
    ann: GeneAnnotation, genome: GenomeSequence, db_manager: DBManager
) -> GeneAnnotation:
    """Adaptive boundary refinement using tblastn against reference protein.

    Runs a local tblastn search using the gene's Protein.fasta reference
    against the genome. If a high-quality hit overlaps the current
    annotation substantially, the tblastn boundaries are adopted.

    Skips trans-spliced/multi-exon genes where tblastn aligns the full
    protein and contiguous hits are not meaningful.
    """
    gene_name_lower = ann.gene_name.lower()

    # Skip trans-spliced genes and any gene with more than one exon
    if gene_name_lower in {k.lower() for k in TRANS_SPLICED_CONFIG} or len(ann.exons) > 1:
        return ann

    tblastn = shutil.which("tblastn")
    makeblastdb = shutil.which("makeblastdb")
    if not tblastn or not makeblastdb:
        return ann

    ref_dir = db_manager.blast_ref_dir
    ref_file = ref_dir / f"{ann.gene_name}.Protein.fasta"
    if not ref_file.exists():
        return ann

    with tempfile.TemporaryDirectory() as tmpdir:
        genome_fa = Path(tmpdir) / "genome.fasta"
        genome_fa.write_text(f">{genome.seqid}\n{genome.sequence}\n")

        db_path = Path(tmpdir) / "genome_db"
        try:
            subprocess.run(
                [makeblastdb, "-in", str(genome_fa), "-dbtype", "nucl", "-out", str(db_path)],
                capture_output=True,
                timeout=60,
                check=True,
            )
        except subprocess.SubprocessError:
            return ann

        out_file = Path(tmpdir) / f"tblastn_{ann.gene_name}.tsv"
        cmd = [
            tblastn,
            "-query", str(ref_file),
            "-db", str(db_path),
            "-out", str(out_file),
            "-outfmt", "6 qseqid sseqid sstart send evalue bitscore pident qcovs",
            "-evalue", "1e-10",
            "-max_target_seqs", "5",
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        except subprocess.SubprocessError:
            return ann

        if not out_file.exists() or not out_file.read_text().strip():
            return ann

        hmm_start = ann.genomic_start
        hmm_end = ann.genomic_end
        hmm_len = hmm_end - hmm_start + 1

        best_hit = None
        best_score = -1.0

        for line in out_file.read_text().strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 8:
                continue
            try:
                sstart = int(parts[2])
                send = int(parts[3])
                bitscore = float(parts[5])
                pident = float(parts[6])
                qcovs = float(parts[7]) if len(parts) > 7 else 0.0
            except (ValueError, IndexError):
                continue

            if pident < 80 or qcovs < 70:
                continue

            hit_start = min(sstart, send)
            hit_end = max(sstart, send)
            hit_len = hit_end - hit_start + 1

            overlap_start = max(hmm_start, hit_start)
            overlap_end = min(hmm_end, hit_end)
            overlap_len = max(0, overlap_end - overlap_start + 1)

            if hmm_len > 0 and overlap_len / hmm_len < 0.8:
                continue

            # Reject hits that would shrink the annotation by >10%.
            # A shorter tblastn hit likely comes from a truncated reference
            # protein and should not override a more accurate boundary.
            if hit_len < hmm_len * 0.9:
                continue

            # Prefer hits closest to the HMM region
            proximity = min(abs(hit_start - hmm_start), abs(hit_end - hmm_end))
            score = bitscore + (100 - proximity) + pident

            if score > best_score:
                best_score = score
                best_hit = (hit_start, hit_end)

    if best_hit:
        new_start, new_end = best_hit
        logger.info(
            f"tblastn refined {ann.gene_name}: {hmm_start}-{hmm_end} -> {new_start}-{new_end}"
        )
        new_exons = [
            ExonRecord(
                start=new_start,
                end=new_end,
                strand=ann.strand,
                number=1,
                phase=0,
            )
        ]
        notes = list(ann.notes)
        notes.append(f"tblastn boundary refinement: {hmm_start}-{hmm_end} -> {new_start}-{new_end}")
        return ann.model_copy(update={
            "exons": new_exons,
            "notes": notes,
            "source_method": "tblastn",
        })

    return ann


def _apply_fixed_offset_correction(ann: GeneAnnotation, genome: GenomeSequence) -> GeneAnnotation:
    """Apply fixed offset correction for genes with systematic position errors.

    Some genes have consistent position offsets across multiple species,
    indicating systematic issues in the annotation pipeline. This function
    applies known corrections.

    Args:
        ann: Gene annotation
        genome: Genome sequence

    Returns:
        Corrected annotation (if gene is in FIXED_OFFSET_GENES)
    """
    gene_name_lower = ann.gene_name.lower()

    if gene_name_lower not in FIXED_OFFSET_GENES:
        return ann

    # Guard: skip BLAST-based annotations from trans-spliced exon refinement
    # (already aligned to reference exons, fixed offsets would destroy accuracy)
    if ann.source_method == "BLAST":
        return ann

    # Guard: skip multi-exon annotations for cox2 (trans-splicing already resolved)
    if gene_name_lower == "cox2" and len(ann.exons) >= 2:
        return ann

    offset_config = FIXED_OFFSET_GENES[gene_name_lower]
    start_offset = offset_config["start_offset"]
    reason = offset_config["reason"]

    if not ann.exons:
        return ann

    # Find the transcription start exon
    if ann.strand == Strand.PLUS:
        # Plus strand: first exon has lowest coordinates
        start_exon_idx = 0
        old_start = ann.exons[0].start
        new_start = old_start + start_offset
        new_start = max(1, new_start)

        ann.exons[start_exon_idx].start = new_start
        logger.info(
            f"Fixed offset for {ann.gene_name}: "
            f"start {old_start} -> {new_start} "
            f"(offset={start_offset}, reason={reason})"
        )
    else:
        # Minus strand: transcription start is the exon with highest coordinates
        # Find exon with highest start (first in transcription order)
        start_exon_idx = max(range(len(ann.exons)), key=lambda i: ann.exons[i].start)
        old_start = ann.exons[start_exon_idx].end
        new_start = old_start - start_offset
        new_start = min(len(genome.sequence), new_start)

        ann.exons[start_exon_idx].end = new_start
        logger.info(
            f"Fixed offset for {ann.gene_name}: "
            f"end {old_start} -> {new_start} "
            f"(offset={start_offset}, reason={reason})"
        )

    return ann


def _get_gene_search_range(gene_name: str, default_range: int) -> int:
    """Get appropriate search range for a gene.
    
    Some genes are known to have issues with boundary prediction
    and need more conservative search ranges.
    """
    # Genes that are prone to over-extension
    CONSERVATIVE_GENES = {
        "atp1", "atp6", "atp8", "atp9",
        "cox1", "cox2", "cox3",
        "cob",
        "ccmB", "ccmC",
        "nad6",
        "matR",
        "mttB",
    }
    
    if gene_name in CONSERVATIVE_GENES:
        return min(default_range, 100)  # Very conservative
    
    return default_range


def _validate_gene_length(ann: GeneAnnotation, db_manager: DBManager) -> GeneAnnotation:
    """Validate gene length against known reference lengths.
    
    If gene is abnormally long or short, add a warning and potentially trim.
    """
    # Known approximate lengths for core genes (in bp)
    EXPECTED_LENGTHS = {
        "atp1": (1400, 1600),
        "atp4": (500, 650),
        "atp6": (900, 1200),
        "atp8": (400, 550),
        "atp9": (200, 280),
        "ccmB": (550, 700),
        "ccmC": (700, 850),
        "ccmFC": (2000, 2500),
        "ccmFN1": (1000, 1300),
        "ccmFN2": (550, 700),
        "cob": (1100, 1300),
        "cox1": (1500, 1650),
        "cox2": (700, 900),
        "cox3": (750, 900),
        "matR": (1800, 2100),
        "mttB": (750, 900),
        "nad1": (900, 1100),  # Total exon length, not span
        "nad2": (1100, 1400),
        "nad3": (300, 400),
        "nad4": (1300, 1600),
        "nad4L": (250, 350),
        "nad5": (1800, 2300),
        "nad6": (550, 700),
        "nad7": (1100, 1400),
        "nad9": (500, 650),
        "rpl2": (900, 1200),
        "rpl5": (500, 650),
        "rpl10": (450, 600),
        "rpl16": (500, 650),
        "rps1": (900, 1200),
        "rps3": (1100, 1500),
        "rps4": (950, 1150),
        "rps7": (400, 550),
        "rps10": (250, 350),
        "rps12": (350, 450),
        "rps14": (280, 380),
        "rps19": (250, 350),
    }
    
    if ann.gene_name not in EXPECTED_LENGTHS:
        return ann
    
    min_len, max_len = EXPECTED_LENGTHS[ann.gene_name]
    current_len = ann.total_exon_length
    
    # If gene is abnormally long, it may have been over-extended
    if current_len > max_len * 1.5:
        logger.warning(
            f"{ann.gene_name}: Abnormal length {current_len}bp "
            f"(expected {min_len}-{max_len}bp). May be over-extended."
        )
        # Don't auto-trim, just flag for now
        notes = ann.notes + [f"Warning: length {current_len}bp exceeds expected range"]
        return ann.model_copy(update={"notes": notes})
    
    # If gene is abnormally short, it may be fragmented
    if current_len < min_len * 0.5:
        logger.warning(
            f"{ann.gene_name}: Abnormal length {current_len}bp "
            f"(expected {min_len}-{max_len}bp). May be fragmented."
        )
        notes = ann.notes + [f"Warning: length {current_len}bp below expected range"]
        return ann.model_copy(update={"notes": notes})
    
    return ann


def _remove_short_introns(
    ann: GeneAnnotation, genome: GenomeSequence
) -> GeneAnnotation:
    """Merge exons separated by very short introns (<150 bp).

    This handles cases like cox2 where a short intron may be
    a false positive from the annotation tool.
    """
    if len(ann.exons) <= 1:
        return ann

    merged_exons = [ann.exons[0]]
    for exon in ann.exons[1:]:
        prev = merged_exons[-1]
        gap = exon.start - prev.end - 1
        if 0 < gap < SHORT_INTRON_THRESHOLD:
            # Merge: extend previous exon to include the gap
            merged_exons[-1] = ExonRecord(
                start=prev.start,
                end=exon.end,
                strand=prev.strand,
                number=prev.number,
            )
        else:
            merged_exons.append(exon)

    if len(merged_exons) < len(ann.exons):
        logger.debug(
            f"  {ann.gene_name}: merged {len(ann.exons)} exons -> {len(merged_exons)}"
        )

    return ann.model_copy(update={"exons": merged_exons})


def _correct_start_codon_conservative(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    db_manager: DBManager,
    search_range: int,
) -> GeneAnnotation:
    """Conservative start codon correction - only adjust if very close to HMM boundary.
    
    Strategy: Trust the HMM hit boundaries more, only make small adjustments
    if a clear start codon is found very close to the boundary.
    """
    if ann.is_pseudo or len(ann.exons) == 0:
        return ann
    
    # Define expected lengths locally
    EXPECTED_LENGTHS = {
        "atp1": (1400, 1600), "atp4": (500, 650), "atp6": (900, 1200), "atp8": (400, 550), "atp9": (200, 280),
        "ccmB": (550, 700), "ccmC": (700, 850), "ccmFC": (2000, 2500), "ccmFN1": (1000, 1300), "ccmFN2": (550, 700),
        "cob": (1100, 1300), "cox1": (1500, 1650), "cox2": (700, 900), "cox3": (750, 900),
        "matR": (1800, 2100), "mttB": (750, 900),
        "nad1": (900, 1100), "nad2": (1100, 1400), "nad3": (300, 400), "nad4": (1300, 1600), "nad4L": (250, 350),
        "nad5": (1800, 2300), "nad6": (550, 700), "nad7": (1100, 1400), "nad9": (500, 650),
        "rpl2": (900, 1200), "rpl5": (500, 650), "rpl10": (450, 600), "rpl16": (500, 650),
        "rps3": (1100, 1500), "rps4": (950, 1150), "rps7": (400, 550), "rps12": (350, 450), "rps14": (280, 380),
    }
    
    # Don't extend genes that are already reasonable length
    current_len = ann.total_exon_length
    logger.debug(f"Boundary correction check for {ann.gene_name}: len={current_len}")
    if ann.gene_name in EXPECTED_LENGTHS:
        min_exp, max_exp = EXPECTED_LENGTHS[ann.gene_name]
        if min_exp * 0.8 <= current_len <= max_exp * 1.2:
            # Length is reasonable, skip correction
            logger.debug(f"{ann.gene_name}: length {current_len} is reasonable, skipping")
            return ann
    
    first_exon = ann.exons[0]
    allowed = _get_allowed_start_codons(ann.gene_name, db_manager)
    
    if ann.strand == Strand.PLUS:
        # For forward strand, look for start codon within small window
        start = first_exon.start
        search_from = max(1, start - search_range)
        
        # Get sequence
        seq = genome.get_sequence_for_range(search_from, first_exon.end)
        if len(seq) < 3:
            return ann
        
        # Calculate frame offset
        offset_in_seq = start - search_from
        frame_offset = offset_in_seq % 3
        
        # Scan backward from HMM start position
        best_start = None
        for i in range(offset_in_seq, -1, -3):
            if i + 2 < len(seq):
                codon = seq[i:i+3].upper()
                if codon in allowed:
                    genome_start = search_from + i
                    # Only accept if within search_range and upstream
                    if genome_start <= start + 3 and abs(genome_start - start) <= search_range:
                        best_start = genome_start
                    break
        
        if best_start and best_start != start:
            new_exons = [ExonRecord(
                start=best_start, end=first_exon.end,
                strand=ann.strand, number=1,
            )]
            new_exons.extend(ann.exons[1:])
            
            note = ""
            codon_at_start = genome.get_sequence_for_range(best_start, best_start + 2).upper()
            if codon_at_start == "ACG":
                note = "RNA editing: ACG->AUG start codon"
            elif codon_at_start not in START_CODONS:
                note = f"non-standard start codon: {codon_at_start}"
            
            updates = {"exons": new_exons}
            if note:
                updates["notes"] = ann.notes + [note]
                updates["exceptions"] = ann.exceptions + ["RNA editing"] if "ACG" in note else ann.exceptions
            return ann.model_copy(update=updates)
    
    else:
        # For reverse strand
        end = ann.exons[-1].end
        search_to = min(genome.length, end + search_range)
        
        fwd_seq = genome.get_sequence_for_range(ann.exons[-1].start, search_to)
        rc_seq = fwd_seq.translate(str.maketrans("ATGCatgcNn", "TACGtacgNn"))[::-1]
        
        if len(rc_seq) < 3:
            return ann
        
        # HMM end position in RC
        hmm_pos_rc = len(fwd_seq) - 1
        frame_offset = hmm_pos_rc % 3
        
        best_offset = None
        for i in range(hmm_pos_rc, -1, -3):
            if i + 2 < len(rc_seq):
                codon = rc_seq[i:i+3].upper()
                if codon in allowed:
                    if i <= hmm_pos_rc + 3:  # Within small range
                        best_offset = i
                    break
        
        if best_offset:
            new_end = ann.exons[-1].start + (len(fwd_seq) - 1 - best_offset)
            if abs(new_end - end) <= search_range:
                new_exons = list(ann.exons[:-1])
                new_exons.append(ExonRecord(
                    start=ann.exons[-1].start, end=new_end,
                    strand=ann.strand, number=ann.exons[-1].number,
                ))
                
                codon_at_start = genome.get_sequence_for_range(new_end - 2, new_end)
                codon_at_start = codon_at_start.translate(str.maketrans("ATGCatgcNn", "TACGtacgNn"))[::-1].upper()
                note = ""
                if codon_at_start == "ACG":
                    note = "RNA editing: ACG->AUG start codon"
                
                updates = {"exons": new_exons}
                if note:
                    updates["notes"] = ann.notes + [note]
                return ann.model_copy(update=updates)
    
    return ann


def _correct_stop_codon_conservative(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    db_manager: DBManager,
    search_range: int,
) -> GeneAnnotation:
    """Conservative stop codon correction - only adjust if very close to HMM boundary."""
    if ann.is_pseudo or len(ann.exons) == 0:
        return ann
    
    # Define expected lengths locally
    EXPECTED_LENGTHS = {
        "atp1": (1400, 1600), "atp4": (500, 650), "atp6": (900, 1200), "atp8": (400, 550), "atp9": (200, 280),
        "ccmB": (550, 700), "ccmC": (700, 850), "ccmFC": (2000, 2500), "ccmFN1": (1000, 1300), "ccmFN2": (550, 700),
        "cob": (1100, 1300), "cox1": (1500, 1650), "cox2": (700, 900), "cox3": (750, 900),
        "matR": (1800, 2100), "mttB": (750, 900),
        "nad1": (900, 1100), "nad2": (1100, 1400), "nad3": (300, 400), "nad4": (1300, 1600), "nad4L": (250, 350),
        "nad5": (1800, 2300), "nad6": (550, 700), "nad7": (1100, 1400), "nad9": (500, 650),
        "rpl2": (900, 1200), "rpl5": (500, 650), "rpl10": (450, 600), "rpl16": (500, 650),
        "rps3": (1100, 1500), "rps4": (950, 1150), "rps7": (400, 550), "rps12": (350, 450), "rps14": (280, 380),
    }
    
    # Don't extend genes that are already reasonable length
    current_len = ann.total_exon_length
    if ann.gene_name in EXPECTED_LENGTHS:
        min_exp, max_exp = EXPECTED_LENGTHS[ann.gene_name]
        if min_exp * 0.8 <= current_len <= max_exp * 1.2:
            return ann
    
    is_stop_gain = db_manager.is_stop_gain_gene(ann.gene_name)
    last_exon = ann.exons[-1]
    
    if ann.strand == Strand.PLUS:
        end = last_exon.end
        # Circular-aware: fetch last exon plus downstream search_range
        downstream_end = ((end + search_range - 1) % genome.length) + 1
        downstream = genome.subsequence(end + 1, downstream_end)
        seq = genome.get_sequence_for_range(last_exon.start, last_exon.end) + downstream

        if len(seq) < 3:
            return ann

        # Calculate frame offset
        prior_len = sum((e.end - e.start + 1) for e in ann.exons[:-1])
        frame_offset = prior_len % 3

        # Look for stop codon
        for i in range(frame_offset, len(seq) - 2, 3):
            codon = seq[i:i+3].upper()
            if codon in STOP_CODONS:
                new_end_raw = last_exon.start + i + 2
                new_end = ((new_end_raw - 1) % genome.length) + 1
                # Accept if downstream within search_range or slightly upstream
                end_diff = genome.circular_span(end, new_end)
                is_downstream = end_diff <= search_range + 3
                is_upstream = (new_end <= end) and (end - new_end <= 3)
                if is_downstream or is_upstream:
                    new_exons = list(ann.exons[:-1])
                    new_exons.append(ExonRecord(
                        start=last_exon.start, end=new_end,
                        strand=ann.strand, number=last_exon.number,
                    ))
                    return ann.model_copy(update={"exons": new_exons})
                break
            if is_stop_gain and codon in STOP_GAIN_CODONS:
                new_end_raw = last_exon.start + i + 2
                new_end = ((new_end_raw - 1) % genome.length) + 1
                end_diff = genome.circular_span(end, new_end)
                is_downstream = end_diff <= search_range + 3
                is_upstream = (new_end <= end) and (end - new_end <= 3)
                if is_downstream or is_upstream:
                    notes = ann.notes + [f"RNA editing: {codon}->stop (C-to-U)"]
                    exceptions = list(set(ann.exceptions + ["RNA editing"]))
                    new_exons = list(ann.exons[:-1])
                    new_exons.append(ExonRecord(
                        start=last_exon.start, end=new_end,
                        strand=ann.strand, number=last_exon.number,
                    ))
                    return ann.model_copy(update={
                        "exons": new_exons, "notes": notes, "exceptions": exceptions
                    })
                break
    
    else:
        # Reverse strand
        start = ann.exons[0].start
        search_from = max(1, start - search_range)
        fwd_seq = genome.get_sequence_for_range(search_from, start + 2)
        rc_seq = fwd_seq.translate(str.maketrans("ATGCatgcNn", "TACGtacgNn"))[::-1]
        
        if len(rc_seq) < 3:
            return ann
        
        for i in range(0, len(rc_seq) - 2, 3):
            codon = rc_seq[i:i+3].upper()
            is_stop = codon in STOP_CODONS
            is_edited_stop = is_stop_gain and codon in STOP_GAIN_CODONS
            if is_stop or is_edited_stop:
                new_start = start - i
                if abs(new_start - start) <= search_range and new_start <= start + 3:
                    notes = list(ann.notes)
                    exceptions = list(ann.exceptions)
                    if is_edited_stop:
                        notes.append(f"RNA editing: {codon}->stop (C-to-U)")
                        exceptions = list(set(exceptions + ["RNA editing"]))
                    new_exons = [ExonRecord(
                        start=new_start, end=ann.exons[0].end,
                        strand=ann.strand, number=1,
                    )]
                    new_exons.extend(ann.exons[1:])
                    updates = {"exons": new_exons}
                    if notes != ann.notes:
                        updates["notes"] = notes
                    if exceptions != list(ann.exceptions):
                        updates["exceptions"] = exceptions
                    return ann.model_copy(update=updates)
                break
    
    return ann


def _correct_start_codon(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    db_manager: DBManager,
    search_range: int,
) -> GeneAnnotation:
    """Find the best start codon for each gene.

    For RNA editing genes (cox1, nad1, nad4L, rps10):
    ACG is accepted as a start codon (edited to AUG).

    For mttB: ATA is accepted.
    For rpl16: GTG is accepted.
    """
    if ann.is_pseudo or len(ann.exons) == 0:
        return ann

    first_exon = ann.exons[0]
    allowed = _get_allowed_start_codons(ann.gene_name, db_manager)

    if ann.strand == Strand.PLUS:
        return _find_start_forward(ann, genome, allowed, search_range)
    else:
        return _find_start_reverse(ann, genome, allowed, search_range)


def _get_allowed_start_codons(gene_name: str, db_manager: DBManager) -> set[str]:
    """Get allowed start codons for a gene."""
    if gene_name in SPECIAL_STARTS:
        return SPECIAL_STARTS[gene_name]
    if db_manager.is_start_gain_gene(gene_name):
        return RNA_EDITING_START
    return START_CODONS


def _find_start_forward(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    allowed: set[str],
    search_range: int,
) -> GeneAnnotation:
    """Find start codon on forward strand with correct reading frame."""
    start = ann.exons[0].start
    search_from = max(1, start - search_range)
    end = ann.exons[-1].end

    # Limit search to not extend beyond reasonable range
    max_search_end = min(genome.length, start + 50)  # Don't extend too far downstream
    
    seq = genome.get_sequence_for_range(search_from, max_search_end)
    if len(seq) < 3:
        return ann

    # Calculate the correct reading frame offset
    # The HMM hit start should be at position (start - search_from) in seq
    # We need to find which offset (0, 1, or 2) puts it in the correct frame
    hmm_offset = (start - search_from) % 3
    
    # Search for start codon upstream of the HMM hit, in the correct frame
    best_start = None
    # Start from the HMM hit position and scan backwards in frame
    hmm_pos = start - search_from  # 0-based position of HMM start in seq
    
    # Scan from HMM start backwards to search_from, stepping by 3
    for i in range(hmm_pos, -1, -3):
        if i + 2 < len(seq):
            codon = seq[i:i+3].upper()
            if codon in allowed:
                genome_start = search_from + i
                # Only accept if it's upstream or close to original start
                if genome_start <= start + 3:  # Allow very small downstream adjustment
                    best_start = genome_start
                    break

    # Also scan a short distance downstream for alternative start
    if best_start is None:
        for i in range(hmm_pos, min(hmm_pos + 9, len(seq) - 2), 3):
            codon = seq[i:i+3].upper()
            if codon in allowed:
                genome_start = search_from + i
                best_start = genome_start
                break

    if best_start is not None and abs(best_start - start) <= search_range:
        new_exons = [ExonRecord(
            start=best_start, end=ann.exons[0].end,
            strand=ann.strand, number=1,
        )]
        new_exons.extend(ann.exons[1:])

        note = ""
        codon_at_start = genome.get_sequence_for_range(best_start, best_start + 2).upper()
        if codon_at_start == "ACG":
            note = "RNA editing: ACG->AUG start codon"
        elif codon_at_start not in START_CODONS:
            note = f"non-standard start codon: {codon_at_start}"

        updates = {"exons": new_exons}
        if note:
            updates["notes"] = ann.notes + [note]
            updates["exceptions"] = ann.exceptions + ["RNA editing"] if "ACG" in note else ann.exceptions
        return ann.model_copy(update=updates)

    return ann


def _find_start_reverse(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    allowed: set[str],
    search_range: int,
) -> GeneAnnotation:
    """Find start codon on reverse strand with correct reading frame.

    On reverse strand, 'start' means the high-coordinate end in genome
    (which is the 5' end of the transcribed gene on the reverse strand).
    """
    end = ann.exons[-1].end  # This is the 5' end on reverse strand
    start = ann.exons[0].start
    search_to = min(genome.length, end + search_range)
    
    # Limit downstream search
    search_to = min(search_to, end + 50)

    # Get forward strand sequence covering the HMM hit and downstream region
    fwd_seq = genome.get_sequence_for_range(start, search_to)
    rc_seq = fwd_seq.translate(str.maketrans("ATGCatgcNn", "TACGtacgNn"))[::-1]
    
    if len(rc_seq) < 3:
        return ann

    # Calculate correct reading frame
    # HMM end is at position (end - start) in fwd_seq
    # In RC, this is at position len(fwd_seq) - 1 - (end - start)
    hmm_pos_in_rc = len(fwd_seq) - 1 - (end - start)
    hmm_offset = hmm_pos_in_rc % 3
    
    # Adjust hmm_pos_in_rc to be at the start of its codon
    hmm_pos_in_rc -= hmm_offset
    
    # Scan from HMM position backwards (towards higher genome coords = 5' end)
    best_offset = None
    for i in range(hmm_pos_in_rc, -1, -3):
        if i + 2 < len(rc_seq):
            codon = rc_seq[i:i+3].upper()
            if codon in allowed:
                # Convert RC position back to genome coordinate
                # RC offset i corresponds to genome position start + (len(fwd_seq) - 1 - i)
                genome_pos = start + (len(fwd_seq) - 1 - i)
                if genome_pos >= end - 3:  # Allow small upstream adjustment
                    best_offset = i
                    break
    
    # If not found, scan a short distance downstream (towards lower genome coords)
    if best_offset is None:
        for i in range(hmm_pos_in_rc, min(hmm_pos_in_rc + 9, len(rc_seq) - 2), 3):
            codon = rc_seq[i:i+3].upper()
            if codon in allowed:
                best_offset = i
                break

    if best_offset is not None:
        # Convert RC offset back to genome coordinate
        genome_end = start + (len(fwd_seq) - 1 - best_offset)
        if abs(genome_end - end) <= search_range:
            new_exons = list(ann.exons[:-1])
            new_exons.append(ExonRecord(
                start=ann.exons[-1].start, end=genome_end,
                strand=ann.strand,
                number=ann.exons[-1].number,
            ))
            # Read the codon at the new start (reverse complement it)
            codon_at_start = genome.get_sequence_for_range(genome_end - 2, genome_end)
            codon_at_start = codon_at_start.translate(
                str.maketrans("ATGCatgcNn", "TACGtacgNn")
            )[::-1].upper()
            note = ""
            if codon_at_start == "ACG":
                note = "RNA editing: ACG->AUG start codon"

            updates = {"exons": new_exons}
            if note:
                updates["notes"] = ann.notes + [note]
            return ann.model_copy(update=updates)

    return ann


def _correct_stop_codon(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    db_manager: DBManager,
    search_range: int,
) -> GeneAnnotation:
    """Find the stop codon for each gene.

    For stop-gain genes (ccmFC, rps10, atp9, atp6, rps11):
    CAA/CAG/CGA codons are accepted as "premature" stops that
    will be edited (C->U) to create proper stop codons.
    """
    if ann.is_pseudo or len(ann.exons) == 0:
        return ann

    is_stop_gain = db_manager.is_stop_gain_gene(ann.gene_name)
    last_exon = ann.exons[-1]

    if ann.strand == Strand.PLUS:
        end = last_exon.end
        search_to = min(genome.length, end + search_range)
        seq = genome.get_sequence_for_range(last_exon.start, search_to)

        # Determine reading frame offset within last exon
        # Total coding length before this exon determines the frame
        prior_coding_len = sum(
            (e.end - e.start + 1) for e in ann.exons[:-1]
        )
        frame_offset = prior_coding_len % 3  # 0, 1, or 2

        # Scan for stop codon in frame, starting at the correct offset
        for i in range(frame_offset, len(seq) - 2, 3):
            codon = seq[i:i+3].upper()
            if codon in STOP_CODONS:
                new_end = last_exon.start + i + 2  # Include stop codon
                if new_end != end:
                    new_exons = list(ann.exons[:-1])
                    new_exons.append(ExonRecord(
                        start=last_exon.start, end=new_end,
                        strand=ann.strand, number=last_exon.number,
                    ))
                    return ann.model_copy(update={"exons": new_exons})
                break
            # Stop-gain: CAA/CAG/CGA treated as edited stop
            if is_stop_gain and codon in STOP_GAIN_CODONS:
                new_end = last_exon.start + i + 2
                notes = ann.notes + [f"RNA editing: {codon}->stop (C-to-U)"]
                exceptions = list(set(ann.exceptions + ["RNA editing"]))
                new_exons = list(ann.exons[:-1])
                new_exons.append(ExonRecord(
                    start=last_exon.start, end=new_end,
                    strand=ann.strand, number=last_exon.number,
                ))
                return ann.model_copy(update={
                    "exons": new_exons,
                    "notes": notes,
                    "exceptions": exceptions,
                })
    else:
        # Reverse strand: stop codon is at the low-coordinate end
        # On reverse strand, the gene reads from high coord to low coord.
        # The stop is near the first exon's start (low coord).
        # We scan from start outward (lower coords) on the reverse complement.
        start = ann.exons[0].start
        search_from = max(1, start - search_range)

        # Get forward strand sequence, then reverse complement
        fwd_seq = genome.get_sequence_for_range(search_from, start + 2)
        rc_seq = fwd_seq.translate(str.maketrans("ATGCatgcNn", "TACGtacgNn"))[::-1]

        # In RC coords: offset 0 = genome position start+2 (5' of gene on RC)
        # Scan toward 3' (which is decreasing genome coords)
        for i in range(0, len(rc_seq) - 2, 3):
            codon = rc_seq[i:i+3].upper()
            is_stop = codon in STOP_CODONS
            is_edited_stop = is_stop_gain and codon in STOP_GAIN_CODONS
            if is_stop or is_edited_stop:
                # RC offset i corresponds to genome end: start+2-i
                # The codon covers genome [start+2-i-2, start+2-i]
                new_start = start - i
                if new_start != start:
                    notes = list(ann.notes)
                    exceptions = list(ann.exceptions)
                    if is_edited_stop:
                        notes.append(f"RNA editing: {codon}->stop (C-to-U)")
                        exceptions = list(set(exceptions + ["RNA editing"]))
                    new_exons = [ExonRecord(
                        start=new_start, end=ann.exons[0].end,
                        strand=ann.strand, number=1,
                    )]
                    new_exons.extend(ann.exons[1:])
                    updates = {"exons": new_exons}
                    if notes != ann.notes:
                        updates["notes"] = notes
                    if exceptions != list(ann.exceptions):
                        updates["exceptions"] = exceptions
                    return ann.model_copy(update=updates)
                break

    return ann


def _handle_special_genes(
    ann: GeneAnnotation,
    genome: GenomeSequence,
    db_manager: DBManager,
) -> GeneAnnotation:
    """Handle gene-specific quirks."""
    name = ann.gene_name

    # rpl16: truncate if first exon is very long AND no valid start codon
    # on the coding strand.  Must be strand-aware: for minus-strand genes
    # the start codon sits at the 3' end (in genome coords).
    if name == "rpl16" and len(ann.exons) >= 1:
        first_len = ann.exons[0].end - ann.exons[0].start + 1
        if first_len > 330:  # >110 aa
            has_start = False
            if ann.strand == Strand.PLUS:
                codon = genome.get_sequence_for_range(
                    ann.exons[0].start, ann.exons[0].start + 2
                ).upper()
            else:
                # Minus strand: start codon is at exon end, reverse-complemented
                raw = genome.get_sequence_for_range(
                    ann.exons[0].end - 2, ann.exons[0].end
                ).upper()
                _rc = str.maketrans("ATGC", "TACG")
                codon = raw.translate(_rc)[::-1]
            if codon in {"ATG", "GTG"}:
                has_start = True

            if has_start:
                logger.debug(f"rpl16: valid start codon {codon}, skipping truncation")
                return ann

            # Scan for nearest ATG/GTG in-frame on the coding strand
            # instead of blind 108bp truncation.
            if ann.strand == Strand.PLUS:
                for offset in range(0, min(150, first_len), 3):
                    pos = ann.exons[0].start + offset
                    c = genome.get_sequence_for_range(pos, pos + 2).upper()
                    if c in {"ATG", "GTG"}:
                        if offset == 0:
                            return ann
                        new_exons = [ExonRecord(
                            start=pos, end=ann.exons[0].end,
                            strand=ann.strand, number=1,
                        )]
                        new_exons.extend(ann.exons[1:])
                        logger.info(f"rpl16: trimmed {offset}bp to reach start codon")
                        return ann.model_copy(update={
                            "exons": new_exons,
                            "notes": ann.notes + [f"rpl16: trimmed {offset}bp to start codon"],
                        })
            else:
                # Minus strand: scan from end toward start
                for offset in range(0, min(150, first_len), 3):
                    pos = ann.exons[0].end - offset
                    raw = genome.get_sequence_for_range(pos - 2, pos).upper()
                    _rc = str.maketrans("ATGC", "TACG")
                    c = raw.translate(_rc)[::-1]
                    if c in {"ATG", "GTG"}:
                        if offset == 0:
                            return ann
                        new_exons = [ExonRecord(
                            start=ann.exons[0].start, end=pos,
                            strand=ann.strand, number=1,
                        )]
                        new_exons.extend(ann.exons[1:])
                        logger.info(f"rpl16: trimmed {offset}bp to reach start codon (minus strand)")
                        return ann.model_copy(update={
                            "exons": new_exons,
                            "notes": ann.notes + [f"rpl16: trimmed {offset}bp to start codon"],
                        })

    # Genes with known N-terminal over-extension from reference proteins.
    # If the gene is longer than the expected maximum, scan forward for an
    # in-frame ATG/GTG that brings the length into the expected range.
    _LENGTH_LIMITED = {
        "rps14": (280, 310),  # NCBI typically 303bp, reference gives ~360bp
        "rps19": (240, 280),  # NCBI typically ~264bp
        "nad6": (600, 650),   # NCBI typically 618bp, reference gives ~669bp
        "rps7": (420, 480),   # NCBI typically 447bp, reference gives ~516bp
        "rps13": (300, 370),  # NCBI typically 351bp, reference gives ~423bp
    }
    if name in _LENGTH_LIMITED and len(ann.exons) >= 1:
        min_len, max_len = _LENGTH_LIMITED[name]
        first_len = ann.exons[0].end - ann.exons[0].start + 1
        if first_len > max_len:
            allowed = _get_allowed_start_codons(name, db_manager)
            _rc = str.maketrans("ATGC", "TACG")
            if ann.strand == Strand.PLUS:
                for offset in range(3, min(150, first_len - min_len), 3):
                    pos = ann.exons[0].start + offset
                    new_len = first_len - offset
                    c = genome.get_sequence_for_range(pos, pos + 2).upper()
                    if c in allowed and min_len <= new_len <= max_len:
                        new_exons = [ExonRecord(
                            start=pos, end=ann.exons[0].end,
                            strand=ann.strand, number=1,
                        )]
                        new_exons.extend(ann.exons[1:])
                        logger.info(f"{name}: trimmed {offset}bp, now {new_len}bp")
                        return ann.model_copy(update={
                            "exons": new_exons,
                            "notes": ann.notes + [f"{name}: trimmed {offset}bp to {new_len}bp"],
                        })
            else:
                for offset in range(3, min(150, first_len - min_len), 3):
                    pos = ann.exons[0].end - offset
                    new_len = first_len - offset
                    raw = genome.get_sequence_for_range(pos - 2, pos).upper()
                    c = raw.translate(_rc)[::-1]
                    if c in allowed and min_len <= new_len <= max_len:
                        new_exons = [ExonRecord(
                            start=ann.exons[0].start, end=pos,
                            strand=ann.strand, number=1,
                        )]
                        new_exons.extend(ann.exons[1:])
                        logger.info(f"{name}: trimmed {offset}bp (minus strand), now {new_len}bp")
                        return ann.model_copy(update={
                            "exons": new_exons,
                            "notes": ann.notes + [f"{name}: trimmed {offset}bp to {new_len}bp"],
                        })

    # nad5: trim over-extended short exon (exon 3).
    # The HMM finds an 82-116bp region where the real exon is only ~22bp.
    # Use the highly conserved 22bp motif to locate the correct boundaries.
    if name == "nad5" and len(ann.exons) >= 3:
        _NAD5_SHORT_EXON_MOTIF = "GATATGATGATTGGTTTAGGTA"
        _NAD5_SHORT_EXON_LEN = 22
        _rc = str.maketrans("ATGC", "TACG")
        motif_rc = _NAD5_SHORT_EXON_MOTIF.translate(_rc)[::-1]
        new_exons = list(ann.exons)
        changed = False
        for idx, exon in enumerate(new_exons):
            exon_len = exon.end - exon.start + 1
            if exon_len < 50 or exon_len > 160:
                continue
            # Get exon sequence from genome
            if exon.strand == Strand.PLUS or exon.strand is None:
                seq = genome.get_sequence_for_range(exon.start, exon.end).upper()
            else:
                raw = genome.get_sequence_for_range(exon.start, exon.end).upper()
                seq = raw.translate(_rc)[::-1]
            # Search for the conserved 22bp motif (allow 1-2 mismatches)
            best_pos = -1
            best_mm = len(_NAD5_SHORT_EXON_MOTIF)
            for i in range(len(seq) - _NAD5_SHORT_EXON_LEN + 1):
                window = seq[i:i + _NAD5_SHORT_EXON_LEN]
                mm = sum(1 for a, b in zip(window, _NAD5_SHORT_EXON_MOTIF) if a != b)
                if mm < best_mm:
                    best_mm = mm
                    best_pos = i
            if best_pos < 0 or best_mm > 2:
                continue
            # Compute new boundaries
            if exon.strand == Strand.PLUS or exon.strand is None:
                new_start = exon.start + best_pos
                new_end = new_start + _NAD5_SHORT_EXON_LEN - 1
            else:
                new_end = exon.end - best_pos
                new_start = new_end - _NAD5_SHORT_EXON_LEN + 1
            old_len = exon.end - exon.start + 1
            trim = old_len - _NAD5_SHORT_EXON_LEN
            if trim < 30:
                continue
            new_exons[idx] = ExonRecord(
                start=new_start, end=new_end,
                strand=exon.strand, number=exon.number,
            )
            changed = True
            logger.info(
                f"nad5: trimmed exon {idx+1} from {old_len}bp to "
                f"{_NAD5_SHORT_EXON_LEN}bp ({trim}bp removed, "
                f"{best_mm} mismatches to motif)"
            )
        if changed:
            return ann.model_copy(update={
                "exons": new_exons,
                "notes": ann.notes + ["nad5: trimmed over-extended short exon"],
            })

    return ann
