"""Long repeat detection via self-BLAST.

Identifies forward, reverse, complementary, and palindromic large repeats
(>100 bp) in plant mitochondrial genomes. These repeats mediate
recombination and generate multi-configuration structures.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from Bio import SeqIO

logger = logging.getLogger(__name__)


@dataclass
class RepeatPair:
    """A pair of repeated regions."""
    repeat_id: str
    type: str           # forward | reverse | complement | palindromic
    copy1_start: int    # 1-based
    copy1_end: int
    copy2_start: int
    copy2_end: int
    length: int         # aligned length
    identity: float     # %
    orientation: str     # direct | inverted
    seqid: str = ""

    @property
    def gap(self) -> int:
        """Distance between the two copies."""
        if self.copy2_start > self.copy1_end:
            return self.copy2_start - self.copy1_end - 1
        elif self.copy1_start > self.copy2_end:
            return self.copy1_start - self.copy2_end - 1
        return 0

    @property
    def is_overlapping(self) -> bool:
        return self.copy1_start <= self.copy2_end and self.copy2_start <= self.copy1_end


@dataclass
class LongRepeatResult:
    """Long repeat detection result."""
    repeat_pairs: list[RepeatPair] = field(default_factory=list)
    genome_length: int = 0

    @property
    def total_repeats(self) -> int:
        return len(self.repeat_pairs)

    def by_type(self) -> dict[str, list[RepeatPair]]:
        cats: dict[str, list[RepeatPair]] = {}
        for r in self.repeat_pairs:
            cats.setdefault(r.type, []).append(r)
        return cats

    def large_repeats(self, min_len: int = 1000) -> list[RepeatPair]:
        """Filter for large repeats (>1kb) that typically mediate recombination."""
        return [r for r in self.repeat_pairs if r.length >= min_len]

    def summary(self) -> str:
        lines = [
            f"Long Repeat Detection",
            f"  Total repeat pairs: {self.total_repeats}",
            f"  Genome length: {self.genome_length:,} bp",
        ]
        for rtype, reps in self.by_type().items():
            lengths = [r.length for r in reps]
            lines.append(
                f"  {rtype}: {len(reps)} pairs "
                f"(max {max(lengths):,} bp, median {sorted(lengths)[len(lengths)//2]:,} bp)"
            )
        large = self.large_repeats()
        if large:
            lines.append(f"  Large repeats (>1kb): {len(large)} — may mediate recombination")
        return "\n".join(lines)


def detect_long_repeats(
    fasta_path: Path,
    output_dir: Path,
    min_length: int = 100,
    min_identity: float = 80.0,
    threads: int = 4,
) -> LongRepeatResult:
    """Detect long repeats via self-BLASTN.

    Args:
        fasta_path: Input genome FASTA
        output_dir: Output directory
        min_length: Minimum repeat length (bp)
        min_identity: Minimum identity %
        threads: Number of threads

    Returns:
        LongRepeatResult
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    record = next(SeqIO.parse(str(fasta_path), "fasta"))
    seq = str(record.seq).upper()
    seqid = record.id
    genome_length = len(seq)

    # Check BLAST+
    makeblastdb = shutil.which("makeblastdb")
    blastn = shutil.which("blastn")

    if makeblastdb and blastn:
        result = _run_self_blast(fasta_path, output_dir, min_length, min_identity, threads)
        if result is not None:
            result.genome_length = genome_length
            return result

    logger.info("BLAST+ not found, using built-in repeat finder")
    return _detect_repeats_python(seq, seqid, min_length, genome_length)


def _run_self_blast(
    fasta_path: Path, output_dir: Path,
    min_length: int, min_identity: float, threads: int,
) -> LongRepeatResult | None:
    """Run self-BLASTN to find repeats."""
    try:
        # Make BLAST database
        db_path = output_dir / "genome_self"
        subprocess.run(
            ["makeblastdb", "-in", str(fasta_path), "-dbtype", "nucl",
             "-out", str(db_path)],
            capture_output=True, text=True, timeout=60,
        )

        # Self-BLASTN
        outfmt = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"
        result = subprocess.run(
            ["blastn", "-query", str(fasta_path), "-db", str(db_path),
             "-outfmt", outfmt, "-evalue", "1e-10",
             "-dust", "no", "-word_size", "11",
             "-num_threads", str(threads),
             "-perc_identity", str(min_identity)],
            capture_output=True, text=True, timeout=300,
        )

        if result.returncode != 0:
            return None

        # Parse results
        repeats = []
        seen = set()
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 12:
                continue

            try:
                qstart, qend = int(parts[6]), int(parts[7])
                sstart, send = int(parts[8]), int(parts[9])
                length = int(parts[3])
                identity = float(parts[2])
            except (ValueError, IndexError):
                continue

            if length < min_length:
                continue

            # Skip self-hits
            if qstart == sstart and qend == send:
                continue

            # Normalize: always store lower coords first
            if qstart > sstart or (qstart == sstart and qend > send):
                qstart, qend, sstart, send = sstart, send, qstart, qend

            # Deduplicate
            key = (qstart, qend, sstart, send)
            if key in seen:
                continue
            seen.add(key)

            # Determine orientation
            # In BLAST output, sstart > send means inverted/complement
            raw_sstart, raw_send = int(parts[8]), int(parts[9])
            if raw_sstart > raw_send:
                orientation = "inverted"
                rtype = "reverse"
            else:
                orientation = "direct"
                rtype = "forward"

            repeat = RepeatPair(
                repeat_id=f"repeat_{len(repeats) + 1}",
                type=rtype,
                copy1_start=qstart,
                copy1_end=qend,
                copy2_start=sstart,
                copy2_end=send,
                length=length,
                identity=identity,
                orientation=orientation,
            )
            repeats.append(repeat)

        return LongRepeatResult(repeat_pairs=repeats)

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"Self-BLAST failed: {e}")
        return None


def _detect_repeats_python(
    seq: str, seqid: str, min_length: int, genome_length: int,
) -> LongRepeatResult:
    """Pure-Python long repeat detection using k-mer matching."""
    # Use hash-based k-mer index for speed
    k = 20  # k-mer size for seeding
    min_kmers = min_length // k

    # Build k-mer index
    kmer_pos: dict[str, list[int]] = {}
    for i in range(len(seq) - k + 1):
        kmer = seq[i:i + k]
        if "N" in kmer:
            continue
        kmer_pos.setdefault(kmer, []).append(i)

    # Find repeated k-mers and extend
    repeats = []
    seen = set()

    for kmer, positions in kmer_pos.items():
        if len(positions) < 2:
            continue
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                p1, p2 = positions[i], positions[j]
                gap = abs(p2 - p1)
                if gap < min_length:
                    continue

                # Extend match
                match_len = k
                while (p1 + match_len < len(seq) and p2 + match_len < len(seq)
                       and seq[p1 + match_len] == seq[p2 + match_len]):
                    match_len += 1

                if match_len < min_length:
                    continue

                start1, start2 = p1 + 1, p2 + 1
                end1, end2 = p1 + match_len, p2 + match_len

                key = (min(start1, start2), max(start1, start2), match_len)
                if key in seen:
                    continue
                seen.add(key)

                if start1 < start2:
                    c1s, c1e, c2s, c2e = start1, end1, start2, end2
                else:
                    c1s, c1e, c2s, c2e = start2, end2, start1, end1

                repeats.append(RepeatPair(
                    repeat_id=f"repeat_{len(repeats) + 1}",
                    type="forward",
                    copy1_start=c1s,
                    copy1_end=c1e,
                    copy2_start=c2s,
                    copy2_end=c2e,
                    length=match_len,
                    identity=100.0,
                    orientation="direct",
                    seqid=seqid,
                ))

    return LongRepeatResult(repeat_pairs=repeats, genome_length=genome_length)


def write_repeat_output(
    result: LongRepeatResult, output_dir: Path, name: str,
) -> dict[str, Path]:
    """Write long repeat results to files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    tsv_path = output_dir / f"{name}_long_repeats.tsv"
    with open(tsv_path, "w") as f:
        f.write("ID\tType\tCopy1Start\tCopy1End\tCopy2Start\tCopy2End\tLength\tIdentity\tOrientation\n")
        for r in result.repeat_pairs:
            f.write(
                f"{r.repeat_id}\t{r.type}\t{r.copy1_start}\t{r.copy1_end}\t"
                f"{r.copy2_start}\t{r.copy2_end}\t{r.length}\t{r.identity:.1f}\t{r.orientation}\n"
            )
    files["tsv"] = tsv_path

    gff_path = output_dir / f"{name}_long_repeats.gff"
    with open(gff_path, "w") as f:
        f.write("##gff-version 3\n")
        for r in result.repeat_pairs:
            for idx, (start, end) in enumerate([(r.copy1_start, r.copy1_end), (r.copy2_start, r.copy2_end)], 1):
                attrs = f"ID={r.repeat_id}_copy{idx};Parent={r.repeat_id};type={r.type}"
                f.write(
                    f"{r.seqid}\tMitoFlow\trepeat_region\t{start}\t{end}\t.\t"
                    f"{'+' if r.orientation == 'direct' else '-'}\t.\t{attrs}\n"
                )
    files["gff"] = gff_path

    return files
