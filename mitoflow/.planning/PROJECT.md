# MitoFlow Round 3 — Annotation Accuracy Improvement

## What This Is

MitoFlow is a plant mitochondrial genome annotation & analysis platform (Python CLI, 17 commands, 92 source files). Round 3 focuses on improving annotation accuracy across three error dimensions: false positive gene detection (A errors), position offset (B errors), and splice site accuracy (C errors). Currently validates at F1=79.5% on 27 gold standard species; target is ≥90%.

## Core Value

Accurate gene annotation — every gene in the right place with the right boundaries. If the annotation is wrong, all downstream analysis (QC, comparative genomics, phylogenetics) is unreliable.

## Requirements

### Validated

- ✓ Full annotation pipeline (PCG/tRNA/rRNA annotation, GFF3/GenBank output)
- ✓ Five-dimensional QC engine
- ✓ Multi-tool comparison framework (PMGA/GeSeq/MFannot/NCBI)
- ✓ Gold standard validation against 27 species (Round 1-2)
- ✓ MitoFlow F1=98.8% on PMGA-benchmarked species (Liriodendron)
- ✓ Duplicate PCG filtering (single-copy enforcement) — Round 2
- ✓ Dynamic trans-spliced config based on genome length — Round 2

### Active

- [ ] Reduce A errors (false positive genes) from 444 to <150
- [ ] Reduce B errors (position offset >50bp) from 263 to <100
- [ ] Reduce C errors (splice site) from 417 to <150
- [ ] Achieve overall F1 ≥90% on 27 gold standard species
- [ ] Fix nad4 systematic 36bp offset across 15 species
- [ ] Handle circular genome coordinate wrapping for multi-exon genes
- [ ] Improve ribosomal protein (rps/rpl) detection specificity

### Out of Scope

- Web interface improvements — separate milestone
- New analysis modules (NUMT, CMS improvements) — not annotation accuracy
- Reference database expansion — Round 4
- RNA editing prediction accuracy — requires experimental data, defer

## Context

### Validation Results (Round 2, 27 species)

| Metric | Round 1 | Round 2 | Target |
|--------|---------|---------|--------|
| Accuracy | 71.96% | 71.86% | ≥90% |
| Sensitivity | 93.04% | 92.94% | ≥95% |
| F1 | 79.56% | 79.51% | ≥90% |
| Exact match (<50bp) | 70.8% | 66.0% | ≥85% |
| A errors | 443 | 444 | <150 |
| B errors | 226 | 263 | <100 |
| C errors | 393 | 417 | <150 |

### Key Error Patterns

**A errors (False Positives)**:
- Top genes: rps19(12 species), mttb(11), sdh4(9), ccmfn(8), rps14(8)
- Worst species: Capsicum annuum(152 errors), Glycine max(65), Cardiocrinum(35)
- Root causes: HMM min_score=30 too low, ribosomal protein overprediction, gene copy handling

**B errors (Position Offset)**:
- Extreme offsets in large genomes (Selenicereus monacanthus, >500kb genome)
- Multi-exon gene coordinate wrapping not handled for circular genomes
- FIXED_OFFSET_GENES table (cox2, rps10, nad7, rps14) not species-adaptive

**C errors (Splice Sites)**:
- nad4: consistent 36bp offset across 15 species — systematic error
- Multi-exon genes (nad1/nad2/nad5/nad7) have highest error rates
- No GT-AG splice site consensus validation

### Existing Codebase

- 92 Python files, 7 test files, Pydantic data models
- Key files: `annotate/pcg.py` (HMM+BLAST), `annotate/boundary.py` (boundary correction), `annotate/trans_splicing.py` (exon merging)
- External tools: pyhmmer, BLAST+, tRNAscan-SE, ARAGORN, Barrnap
- Reference data bundled in `src/mitoflow/data/`

## Constraints

- **Python 3.10+**: No async, all synchronous pipeline
- **Offline**: No web APIs, all tools must be local
- **Circular genomes**: Plant mitochondrial genomes are circular — coordinate math must handle wrapping
- **Backwards compatible**: Existing CLI interface must not change
- **Test before batch**: Fix one species at a time, validate, then expand

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Target F1 ≥90% (not 95%) | PMGA achieves 97.4% but uses RNA-seq; MitoFlow is annotation-only so 90% is realistic | — Pending |
| Focus on core 41 PCG genes | tRNA/rRNA handled by external tools (tRNAscan-SE, Barrnap); PCG annotation is MitoFlow's core | — Pending |
| Keep validation against NCBI gold standard | PMGA data not available for all 27 species; NCBI is the universal baseline | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-14 after initialization*
