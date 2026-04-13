"""Gene boundary correction.

Translates PMGA v1 logic from 02.editBoundary.py:
- Exon-intron boundary adjustment via sliding window
- Start codon correction (ACG->AUG RNA editing)
- Stop codon correction (CAA->UAA RNA editing for stop-gain genes)
- Short intron removal (<150 bp)
- rpl16 truncation handling
- Multi-exon gene processing
"""

from __future__ import annotations
import logging
from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation, ExonRecord, Strand
from ..db.manager import DBManager
from .pcg import CODON_TABLE, START_CODONS, STOP_CODONS

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


def correct_boundaries(
    annotations: list[GeneAnnotation],
    genome: GenomeSequence,
    db_manager: DBManager,
    search_range: int = 30,  # Very conservative: only 30bp adjustment
) -> list[GeneAnnotation]:
    """Apply all boundary corrections to annotations.

    Steps:
    1. Remove short introns (merge exons separated by <150 bp)
    2. Correct start codons (search upstream for ATG/ACG) - CONSERVATIVE
    3. Correct stop codons (search downstream for stop) - CONSERVATIVE
    4. Handle rpl16 truncation
    5. Handle special start codons (mttB ATA, etc.)

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
        # Only do minimal boundary correction - trust HMM hit more
        ann = _correct_start_codon_conservative(ann, genome, db_manager, gene_search_range)
        ann = _correct_stop_codon_conservative(ann, genome, db_manager, gene_search_range)
        ann = _handle_special_genes(ann, genome, db_manager)
        ann = _validate_gene_length(ann, db_manager)
        corrected.append(ann)
    return corrected


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
        search_to = min(genome.length, end + search_range)
        seq = genome.get_sequence_for_range(last_exon.start, search_to)
        
        if len(seq) < 3:
            return ann
        
        # Calculate frame offset
        prior_len = sum((e.end - e.start + 1) for e in ann.exons[:-1])
        frame_offset = prior_len % 3
        
        # Look for stop codon
        for i in range(frame_offset, len(seq) - 2, 3):
            codon = seq[i:i+3].upper()
            if codon in STOP_CODONS:
                new_end = last_exon.start + i + 2
                if abs(new_end - end) <= search_range and new_end >= end - 3:
                    new_exons = list(ann.exons[:-1])
                    new_exons.append(ExonRecord(
                        start=last_exon.start, end=new_end,
                        strand=ann.strand, number=last_exon.number,
                    ))
                    return ann.model_copy(update={"exons": new_exons})
                break
            if is_stop_gain and codon in STOP_GAIN_CODONS:
                new_end = last_exon.start + i + 2
                if abs(new_end - end) <= search_range:
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

    # rpl16: truncate if first exon is very long (>110 aa)
    # BUT only if no start codon was found by boundary refinement
    # If position starts with ATG/GTG, don't truncate
    if name == "rpl16" and len(ann.exons) >= 1:
        first_len = ann.exons[0].end - ann.exons[0].start + 1
        if first_len > 330:  # >110 aa
            # Check if the exon starts with a valid start codon
            start_codon = genome.get_sequence_for_range(
                ann.exons[0].start, ann.exons[0].start + 2
            ).upper()
            allowed_starts = {"ATG", "GTG"}
            if start_codon in allowed_starts:
                # Start codon already found by tblastn, don't truncate
                logger.debug(f"rpl16: starts with {start_codon}, skipping truncation")
                return ann

            # Otherwise, truncate first 108bp (common rpl16 issue)
            new_start = ann.exons[0].start + 108
            new_exons = [ExonRecord(
                start=new_start, end=ann.exons[0].end,
                strand=ann.strand, number=1,
            )]
            new_exons.extend(ann.exons[1:])
            logger.info(f"rpl16: truncating first 108bp (no start codon at position)")
            return ann.model_copy(update={
                "exons": new_exons,
                "notes": ann.notes + ["rpl16: truncated first 108 bp"],
            })

    return ann
