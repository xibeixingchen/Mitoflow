# Testing — MitoFlow

**Mapped:** 2026-04-14

## Framework

- **pytest** with `pytest-cov` for coverage
- Config in `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["src"]`

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_input.py                  # FASTA input validation
├── test_boundary_refinement.py    # Gene boundary correction
├── test_trans_splicing.py         # Trans-spliced gene detection
├── test_trans_splicing_merge.py   # Exon merging for trans-spliced genes
├── test_trna_naming.py            # tRNA gene naming conventions
├── test_gene_length_validation.py # Gene length checks
└── test_data/                     # Test input files
```

## Coverage

- **7 test files** covering core annotation functionality
- No tests for: QC, MTPT, RNA editing, codon, Ka/Ks, phylo, synteny, repeat, NUMT, CMS, multiconf
- Coverage data tracked in `.coverage` file
- Coverage is currently focused on annotation pipeline, not downstream analysis

## Test Scope

| Module | Tested | Notes |
|--------|--------|-------|
| Core (input, pipeline) | Partial | `test_input.py` only |
| Annotate (pcg, trna, rrna) | Partial | Via boundary/trans-splicing tests |
| Annotate (boundary) | Yes | `test_boundary_refinement.py` |
| Annotate (trans-splicing) | Yes | `test_trans_splicing.py`, `test_trans_splicing_merge.py` |
| Annotate (tRNA naming) | Yes | `test_trna_naming.py` |
| QC | No | No test files |
| MTPT | No | No test files |
| RNA editing | No | No test files |
| Codon | No | No test files |
| Ka/Ks | No | No test files |
| Phylo | No | No test files |
| Synteny | No | No test files |
| All other modules | No | No test files |

## Integration Testing

- Gold standard validation via `scripts/run_gold_standard_batch.sh`
- Test data in `data/gold_standard/` (~30+ reference GenBank files)
- Batch comparison framework in recent commits

## Test Fixtures

- `conftest.py` provides shared fixtures
- `test_data/` contains sample input files

## Running Tests

```bash
pytest                    # Run all tests
pytest --cov=mitoflow     # With coverage
pytest tests/test_input.py  # Specific test file
```
