# Concerns — MitoFlow

**Mapped:** 2026-04-14

## Test Coverage Gaps

**Severity: High**

- 7 test files for 92 source files — most modules have zero tests
- No tests for: QC engine, MTPT detection, RNA editing, codon analysis, Ka/Ks, phylo, synteny, repeat detection, NUMT detection, CMS prediction, multi-configuration
- Downstream analysis modules are completely untested
- Risk: regressions in analysis modules go undetected

## External Tool Dependencies

**Severity: Medium**

- 10+ external CLI tools required (tRNAscan-SE, ARAGORN, Barrnap, BLAST+, minimap2, samtools, MAFFT, trimAl, IQ-TREE, KaKs_Calculator, Rscript)
- No version pinning — any version in PATH is used
- No graceful degradation — missing tools cause hard failures
- Installation burden is high for new users
- Some tools may not be available on all platforms

## Database Management

**Severity: Medium**

- `db build` and `db download` commands are TODO stubs
- Reference data is bundled in `src/mitoflow/data/` (committed to git)
- Multiple versions of PCG references (`pcg/`, `pcg_new/`, `pcg_v2/`, `pcg/backup_old/`) suggest evolution without cleanup
- No database versioning or migration system

## Code Duplication

**Severity: Medium**

- Every analysis module has nearly identical `visualize.py` + `visualize_r.py` pattern
- CLI commands follow similar boilerplate: load input, run analysis, write report, optional plot
- Visualization code likely has significant duplication across modules
- Pattern could benefit from a shared base class or utility functions

## Subprocess Error Handling

**Severity: Low-Medium**

- External tools called via `subprocess.run()` but error handling varies
- Some commands check `returncode`, others may not
- Timeout handling inconsistent (phylo-tree has 3600s timeout, others may not)
- stderr output sometimes truncated (`proc.stderr[-500:]`)

## Configuration Management

**Severity: Low**

- Pipeline parameters hardcoded as defaults in CLI (`threads=4`, `evalue=1e-5`)
- No config file support for pipeline settings
- Genetic code table hardcoded to Table 1 (standard) — plant mitochondria may need Table 2 or others

## Web Interface

**Severity: Low**

- `deploy/web/backend/main.py` and `deploy/web/frontend/app.py` exist but appear to be scaffolding
- No indication of active development or testing for web interface

## R Visualization Dependency

**Severity: Low**

- Dual visualization (Python + R) adds complexity
- R scripts called via subprocess — error handling may be inconsistent
- OGDrawR is a custom R package (not on CRAN) — installation friction

## Performance

**Severity: Low**

- Single genome processing — no built-in parallelism across genomes
- HMM searches can be slow for large genomes
- No caching of intermediate results between pipeline runs

## Documentation

**Severity: Low**

- README exists (English + Chinese)
- Inline docstrings present but inconsistent
- No API documentation generation (no Sphinx/MkDocs)
- `docs/` directory exists but content unknown
