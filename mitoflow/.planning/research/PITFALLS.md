# Pitfalls Research — MitoFlow Round 3

**Researched:** 2026-04-14

## Pitfall 1: Over-Filtering True Genes

**Description**: Raising HMM thresholds too high will eliminate false positives BUT also remove real genes, dropping sensitivity below the 93% baseline.

**Warning Signs**:
- Sensitivity drops below 90% after threshold changes
- Species that were perfect (Ipomoea, Solanum) start losing genes
- Core genes (cox1, atp1) missing in some species

**Prevention**:
- Per-gene thresholds, not blanket increases
- Always check sensitivity alongside accuracy
- Test on high-F1 species (Ipomoea, Solanum, Punica) first — they must stay at 100%
- **Phase: Phase 1 (threshold changes)**

## Pitfall 2: Circular Coordinate Off-By-One

**Description**: Modular arithmetic for circular coordinates is tricky. Off-by-one errors in `(end - start) % length` calculations can shift ALL positions by 1bp.

**Warning Signs**:
- All genes in a species shift by exactly 1bp
- Genes that span origin show wrong boundaries
- Tests fail on edge cases (gene exactly at position 1 or genome_length)

**Prevention**:
- Use 1-based coordinates consistently (MitoFlow convention)
- Write unit tests for circular_distance with known values
- Test: circular_distance(1, genome_length, genome_length) == 0 or 1
- **Phase: Phase 1 (circular utilities)**

## Pitfall 3: False Gold Standard Assumptions

**Description**: Some NCBI annotations are incomplete or wrong. "Fixing" MitoFlow to match bad NCBI annotations makes it worse.

**Example**: Cardiocrinum giganteum has only 4 NCBI-annotated genes but plant mitochondria have 30-41 PCG genes. MitoFlow correctly finds 39 genes but gets penalized for 35 "false positives".

**Warning Signs**:
- Accuracy drops after "improvements" because we're matching bad annotations
- Species with <15 genes in gold standard have terrible F1

**Prevention**:
- Track which A errors are in "low-confidence" species (<15 NCBI genes)
- Don't optimize for these species — optimize for well-annotated ones
- Consider weighted metrics that down-weight poorly-annotated species
- **Phase: Phase 1 (validation fix)**

## Pitfall 4: Breaking Multi-Exon Genes While Fixing Others

**Description**: Changes to trans_splicing.py or boundary.py that fix one gene may break another. Round 2's dynamic span changes helped some species but hurt others.

**Warning Signs**:
- Species that improved in one gene regress in another
- nad4 fix causes nad5 or nad2 to break
- Changing max_span parameters has unpredictable effects

**Prevention**:
- Per-species regression testing after each change
- Track ALL 27 species, not just the ones being "fixed"
- Make changes gene-specific, not global parameter changes
- **Phase: Phase 2 (multi-exon fixes)**

## Pitfall 5: Splice Site Validation Being Too Strict

**Description**: Adding GT/AG consensus validation may reject real exons. Plant mitochondrial introns include both group II (GT/AG typical) and some non-canonical boundaries.

**Warning Signs**:
- Exon count drops after adding splice site checks
- Genes that were correctly detected lose exons
- Sensitivity decreases

**Prevention**:
- Use splice site scores as penalties, not hard filters
- Allow GC/AG as alternative consensus
- Only apply to high-confidence exon boundaries
- **Phase: Phase 2 (splice site fixes)**

## Pitfall 6: Changing Validation Metrics Without Noting It

**Description**: If we change the validation script to use circular distance, B errors will drop dramatically. But this is a metric change, not an annotation improvement.

**Warning Signs**:
- B errors drop but actual gene positions don't change
- Reporting "improvement" that's just different measurement

**Prevention**:
- Always report both "old metric" and "new metric" results
- Separate validation improvements from annotation improvements
- Be honest about what changed
- **Phase: Phase 1 (validation fix)**

## Pitfall 7: Not Testing Incrementally

**Description**: Making all changes at once makes it impossible to know which change helped or hurt.

**Warning Signs**:
- Can't explain why metrics changed
- Overall improvement but regression in specific species

**Prevention**:
- One change at a time with validation after each
- Git commit after each tested change
- Track per-species metrics, not just averages
- **Phase: All phases**
