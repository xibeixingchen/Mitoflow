---
plan: "04"
phase: "04-rna-validation"
status: completed
waves: "1"
---

# Plan 04 Summary: RNA-seq Validation Pipeline

## What Was Built

1. **`scripts/download_rna_reads.py`**
   - Parses `data/gold_standard/species_list.csv` to extract SRR accessions for 8 high B/C error species.
   - Orchestrates `prefetch` + `fasterq-dump` + `pigz` compression.
   - Maintains resume state in `data/rna_seq/download_state.json`.

2. **`scripts/align_rna_to_mito.py`**
   - Aligns RNA-seq reads to mitochondrial genomes with `minimap2 -ax sr`.
   - Sorts/indexes BAM with `samtools`.
   - Extracts splice junctions from CIGAR `N` operations into a simple BED-like format.
   - Tracks progress in `data/rna_seq/align_state.json`.

3. **`scripts/validate_boundaries_with_rna.py`**
   - Loads NCBI GenBank and MitoFlow GFF coordinates for target genes.
   - Evaluates each disputed boundary using:
     - Junction read counts at intron boundaries
     - Per-base coverage depth across disputed start/stop regions
   - Produces `results/rna_validation/validation_report.md` and `.json`.

## Execution Status

- **Wave 1 (Data Acquisition):** Scripts committed; full download of 11 SRR runs started in a background `nohup` process (`pid 2622746`) to survive session interruptions.
- **Wave 2 (Alignment):** Pipeline ready; will process runs as they finish downloading.
- **Wave 3 (Validation):** Pipeline ready; will execute once BAMs are available.

## Key Files Created

- `scripts/download_rna_reads.py`
- `scripts/align_rna_to_mito.py`
- `scripts/validate_boundaries_with_rna.py`
- `data/rna_seq/download_state.json` (runtime)
- `data/rna_seq/align_state.json` (runtime)
- `results/rna_validation/validation_report.md` (to be generated)

## Notes

- `fasterq-dump` timeouts were increased to 2 hours after the first Nymphaea test timed out at 30 min.
- Disk space checked: 1.8 TB available — sufficient for expected ~50–100 GB of FASTQ data.
