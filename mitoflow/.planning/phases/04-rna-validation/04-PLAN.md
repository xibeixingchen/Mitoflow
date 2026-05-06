---
phase: 04-rna-validation
gap_closure: false
requirements:
  - VAL-04
  - BPS-04
  - CSP-04
target_species:
  - Camellia sinensis var. assamica (SRR13425452)
  - Nymphaea hybrid cultivar 'Joey Tomocik' (SRR15402843)
  - Liriodendron tulipifera (SRR9849700, SRR9849652, SRR16546803)
  - Eucommia ulmoides (SRR23055733)
  - Pontederia crassipes (SRR26510776)
  - Selenicereus monacanthus (SRR24044980)
  - Glycine max (SRR8447156)
  - Capsicum annuum cultivar Jeju (SRR12417747)
---

# Phase 4: RNA-seq Validation of Disputed Boundaries

**Goal:** 使用公开 RNA-seq 数据验证 Phase 3 中高 B/C 错误物种的线粒体基因边界，判断 MitoFlow 与 NCBI 官方注释孰是孰非。

**Context:**
- Phase 3 后 B-error 仍较高的物种集中在大基因组物种（Camellia 31, Nymphaea 16, Liriodendron 14）。
- 这些物种的 NCBI 注释可能本身存在系统性偏差（尤其是跨物种同源转移注释）。
- `species_list.csv` 中已提供了对应物种的 SRA Run 编号，可直接用于下载。

**Target Genes (high B/C error across these species):**
- `cox2` (cis-spliced, 2 exons)
- `nad5` (trans-spliced, 5 exons)
- `rpl16` (truncation, start codon boundary)
- `nad1`, `nad2`, `nad4`, `nad7` (trans-spliced)
- `atp6`, `cox3`, `rps4` (frequent boundary deviation)

---

## Wave 1: Data Acquisition

### Plan 01: Download and prepare RNA-seq reads

**Files to create/modify:**
- `scripts/download_rna_reads.py` — 根据 `species_list.csv` 批量下载 SRA
- `data/rna_seq/` — 存放 FASTQ

**Changes:**
1. Parse `data/gold_standard/species_list.csv` to extract SRR accessions for target species.
2. Use `prefetch` + `fasterq-dump` (sratoolkit) to download reads.
3. Compress with `pigz`.
4. Track download status in `data/rna_seq/download_state.json` (checkpoint/resume).

**Verification:**
- All target SRRs have non-empty `.fastq.gz` files.
- `download_state.json` reports success/failure per run.

---

## Wave 2: Alignment and Junction Extraction

### Plan 02: Align RNA-seq to mitochondrial genomes

**Files to create/modify:**
- `scripts/align_rna_to_mito.py`
- `data/rna_seq/bam/` — 输出 BAM
- `data/rna_seq/junctions/` — 输出 junction BED

**Changes:**
1. For each species, build minimap2 index from `data/gold_standard/fasta/{species}.fasta`.
2. Align paired-end reads with `minimap2 -ax sr` (fallback to `hisat2` if splice-aware needed).
3. Sort and index BAM with `samtools`.
4. Extract splice junctions using `samtools view` + custom parser (looking for N in CIGAR >10bp).
5. Convert junctions to BED12-like format: `chrom start end strand intron_len left_motif right_motif n_reads`.

**Verification:**
- BAM files have >1M mapped reads per species (or report low coverage).
- Junction BED is non-empty for spliced species.

---

## Wave 3: Boundary Validation

### Plan 03: Compare MitoFlow vs NCBI boundaries using RNA support

**Files to create/modify:**
- `scripts/validate_boundaries_with_rna.py`
- `results/rna_validation/validation_report.md`
- `results/rna_validation/per_gene_plots/` (optional, using matplotlib)

**Changes:**
1. For each target gene in each species:
   a. Load MitoFlow GFF and NCBI GenBank CDS coordinates.
   b. Query RNA coverage over the gene region using `samtools depth`.
   c. Check junction reads spanning introns (for multi-exon genes):
      - MitoFlow intron boundaries vs NCBI intron boundaries.
      - Count reads supporting each boundary.
   d. Check coverage drop at start/stop codon regions:
      - If NCBI boundary extends into intergenic and coverage drops to zero, NCBI likely over-extended.
      - If MitoFlow boundary is short and coverage continues, MitoFlow likely under-extended.
2. Score each disputed boundary:
   - `strong_support_mitoflow`: ≥5 junction reads or continuous coverage match MitoFlow boundary.
   - `strong_support_ncbi`: ≥5 junction reads or continuous coverage match NCBI boundary.
   - `ambiguous`: conflicting or insufficient evidence.
   - `both_wrong`: neither boundary matches RNA evidence.
3. Output per-species and per-gene tables.

**Verification:**
- Report contains quantitative counts for each support category.
- At least 3 genes have unambiguous RNA support for one annotation over the other.

---

## Wave 4: Integration and Reporting

### Plan 04: Update validation metrics and STATE

**Files to modify:**
- `.planning/STATE.md`
- `results/phase3_quick_batch_validation/validation_report.md` (append RNA validation section)

**Changes:**
1. If RNA evidence supports MitoFlow boundaries for a substantial fraction of disputed genes, reclassify those B/C errors as "NCBI annotation error" rather than MitoFlow error.
2. Update STATE.md with Phase 4 results and revised error counts.
3. If RNA supports NCBI, create fix plans for those genes and enter gap-closure mode.

**Verification:**
- STATE.md reflects RNA-adjusted B/C error counts.
- Decision documented on whether to proceed with code fixes or accept current boundaries.

---

## Success Criteria

1. All 8 target species RNA-seq datasets downloaded and aligned.
2. Junction extraction pipeline runs end-to-end without errors.
3. Quantitative boundary support scores for ≥20 disputed gene boundaries.
4. Clear classification of how many B/C errors are genuine MitoFlow bugs vs NCBI annotation errors.
5. STATE.md updated with revised assessment.

---

## Execution Order

| Wave | Plan | Scope | Key Deliverable |
|------|------|-------|-----------------|
| 1 | 01 | Download SRA reads | `data/rna_seq/*.fastq.gz` |
| 2 | 02 | Alignment + junction extraction | `data/rna_seq/bam/*.bam`, `junctions/*.bed` |
| 3 | 03 | Boundary validation with RNA | `results/rna_validation/validation_report.md` |
| 4 | 04 | STATE update + revised metrics | Updated `.planning/STATE.md` |

---

## Risk Flags

- **R1: SRA data may be nuclear-enriched, low mitochondrial coverage**
  - Mitigation: accept ≥100k mapped reads; report coverage depth explicitly.
- **R2: Plant mitochondrial RNA editing may obscure exact boundaries**
  - Mitigation: focus on exon-intron junctions (unaffected by C-to-U editing) and use cumulative coverage rather than codon-level precision.
- **R3: Large download sizes / slow network**
  - Mitigation: checkpoint with `download_state.json`; support `--resume` and `--species` subset flags.
