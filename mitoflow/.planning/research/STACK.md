# Stack Research — MitoFlow Round 3

**Researched:** 2026-04-14

## Current Approach Assessment

MitoFlow uses pyhmmer (HMM profiles) as primary gene detection with BLAST+ tblastn as boundary refinement. This is a sound two-stage approach, but thresholds and post-processing need tuning.

## HMM Detection Best Practices

### Score Thresholds

| Gene Category | Recommended min_score | Current | Confidence |
|---------------|----------------------|---------|------------|
| Core PCG (nad/cox/atp/cob) | 50.0 | 30.0 | High |
| Ribosomal proteins (rps/rpl) | 60.0 | 30.0 | High |
| ccm genes | 40.0 | 30.0 | Medium |
| matR/sdh/mttB | 40.0 | 30.0 | Medium |

**Rationale**: Ribosomal proteins (rps/rpl) are the top false-positive category (rps19=12 species, rps14=8). Higher thresholds for this family will reduce overprediction without losing real genes. Core oxidative phosphorylation genes (nad/cox/atp) have stronger conservation and can use lower thresholds.

### E-value Threshold

- Current: 1e-5 — appropriate for plant mitochondrial genomes
- No change needed

### Length Filtering

- Current: min 30aa (90bp), max 2500aa
- Recommendation: **Per-gene length filtering** based on expected ranges
- Genes <50% or >150% of expected length should be flagged as suspicious, not rejected outright
- **Confidence: High**

## Boundary Correction Methods

### Start Codon Detection

Current approach searches ±30bp for start codons. Recommendations:

1. **Extending ATG search to include GTG/TTG/ATA/ACG** for mitochondrial genes (already partially implemented)
2. **RNA editing-aware start codon detection**: Genes with C-to-U RNA editing may use non-ATG starts that become ATG after editing (e.g., ACG→ATG for rps4)
3. **Search range should be per-gene**: Core genes ±30bp, problematic genes ±100bp, with upper cap at 300bp
4. **Confidence: High**

### Stop Codon Detection

- Include RNA editing-aware stops: CAA→TAA, CAG→TAG, CGA→UGA via C-to-U editing
- Current STOP_GAIN_CODONS set is correct
- **Confidence: High**

### Circular Genome Coordinate Handling

**Critical missing feature**. Plant mitochondrial genomes are circular. When a gene spans the "origin" (position 0/L), coordinates wrap around. For example, a gene at positions 490,000-10,000 in a 500,000bp genome.

Implementation approach:
- `circular_distance(start, end, genome_length)` — computes minimum distance accounting for wrap-around
- `circular_span(start, end, genome_length)` — computes span (forward direction)
- Use modular arithmetic: `(end - start) % genome_length`
- Apply to: exon merging, boundary correction, position comparison
- **Confidence: High** — this is a well-known problem with established solutions

## Multi-Exon Gene Handling

### Exon Merging

Current approach uses score-based selection. Recommendations:

1. **Add splice site consensus validation**: Check GT/AG (or GC/AG) at exon-intron boundaries
2. **Reading frame continuity**: Ensure codon phases match between exons
3. **Per-gene exon count validation**: nad1=5, nad2=5, nad5=5, nad4=4, nad7=4, etc.
4. **Confidence: High**

### nad4 Systematic Error

The 36bp offset across 15 species strongly suggests a specific bug:
- Likely an off-by-one in codon position calculation
- Or a missing exon boundary correction for nad4 specifically
- Check if nad4 exon 1 is being truncated/extended by exactly 36bp (12 codons)
- **Confidence: High** — systematic errors always have systematic causes

## tblastn Refinement

Current approach extends ±200bp around HMM hit with scoring formula `bitscore + (500 - proximity) + pident`. Recommendations:

1. **Prioritize full-length alignments** over partial ones
2. **Use protein coverage** as primary selection criterion (should cover ≥80% of reference protein)
3. **Validate against expected gene length** — reject tblastn hits that produce genes >2x expected
4. **Confidence: Medium**

## Validation Framework

### Gold Standard Quality

The current 27-species gold standard has quality issues:
- Some NCBI annotations have very few genes (Cardiocrinum: 4 genes, Angelica: 9 genes)
- These drag down accuracy metrics unfairly
- Recommendation: **Weighted scoring** — exclude species with <15 annotated genes from A-error calculation
- **Confidence: Medium**

### Position Comparison

Current comparison uses simple linear distance. For circular genomes:
- Must use `min(|a-b|, genome_length - |a-b|)` for distance calculation
- This alone could fix many B errors in large genomes
- **Confidence: High**
