# Quality Control Skill

## Contract

Assess annotation quality on five dimensions: completeness, boundary accuracy,
splice site correctness, tRNA/rRNA validity, and structural integrity.
Compare against gold standard when available.

## Quality Dimensions

### 1. Completeness
- Expected gene count: ~40–60 (varies by species)
- Core set: 24 PCGs conserved across land plants
- BUSCO assessment

### 2. Boundary Accuracy
- Start/stop codon correctness
- Coverage drop-off validation at gene ends
- Gold standard comparison (when available)

### 3. Splice Site Accuracy
- Canonical GT-AG for cis-spliced introns
- Correct exon order for trans-spliced genes
- Exon boundaries validated by coverage

### 4. tRNA/rRNA Validity
- tRNAscan-SE confidence scores
- ARAGORN cross-validation
- Barrnap rRNA boundaries

### 5. Structural Integrity
- Circular genome → no truncation
- Gene order consistency
- Repeat boundaries correct

## Error Classification

| Error Type | Description | Typical Cause |
|------------|-------------|---------------|
| **A errors** | False positive genes | Low e-value threshold, NUMT contamination |
| **B errors** | Boundary offset | Incorrect start/stop, poor coverage |
| **C errors** | Splice site errors | Wrong GT-AG, trans-splicing misassembly |

## Command Template

```bash
mitoflow qc -i results/ --gold-standard reference.gb
```

## Performance Targets

- F1 ≥ 90%: Production quality
- F1 80–90%: Needs improvement
- F1 < 80%: Significant issues

## References

- Current MitoFlow accuracy: 90.5% F1 on 27 gold standard species
