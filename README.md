# PMGA - Plant Mitochondrial Genome Annotator

A containerized plant mitochondrial genome annotation tool based on MGAVAS, packaged as an Apptainer/Singularity image.

## Features

- Automatic annotation of protein-coding genes (CDS)
- tRNA and rRNA gene identification
- Repeat sequence analysis (SSR, Tandem Repeats)
- Generation of GenBank (.gbf) and GFF3 (.gff) annotation files
- Circular genome map visualization
- Codon usage analysis report

## Bug Fixes (v1.0)

This version includes the following fixes compared to the original MGAVAS:

### Core Fixes

1. **GFF File Generation Issue**
   - Fixed the issue where GFF file was not generated when `mergeGFFFiles` function failed
   - Added automatic fallback mechanism to copy `_anno3.gff` to `.gff`

2. **Missing merged.fas File**
   - Fixed the issue where `_merged.fas` file was not created for single contig input
   - Automatically creates required merged files from input sequence

3. **merged_stat.txt Format Error**
   - Fixed `04.tRNAIdentify.py` parsing error (`ValueError: invalid literal for int()`)
   - Changed file format to correct 3-column format (without header)

4. **LOCUS Line Format Overflow**
   - Fixed GenBank LOCUS line format error caused by long species names
   - Recommend using short project names (e.g., `Ranunculus` instead of `Ranunculus_cassubicifolius`)

### Added Perl Modules

Added the following missing Perl modules for full functionality:

- XML::Generator, XML::Simple, XML::Writer
- Config::General
- GD, GD::Polyline, GD::SVG, SVG
- Math::Bezier, Math::Round, Math::VecStat
- Set::IntSpan, Statistics::Basic
- Font::TTF::Font
- Other Circos plotting dependencies

### Other Improvements

- Added error suppression to avoid unnecessary warning output
- Optimized file organization steps

## Installation

### Download Image
```bash
# Download PMGA.sif from GitHub Releases
wget https://github.com/xibeixingchen/PMGA/releases/download/v1.0/PMGA.sif
```

## Usage
```bash
# Using Apptainer/Singularity
apptainer exec --bind /path/to/data:/path/to/data PMGA.sif \
    /apps/mgavas/bin/mgavas_m \
    -pid ProjectName \
    -in /path/to/input.fasta \
    -db 4 \
    -outdir /path/to/output
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `-pid` | Project name (recommend short names, e.g., genus name) |
| `-in` | Input mitochondrial genome FASTA file |
| `-db` | Database selection (4 = plant mitochondrial database) |
| `-outdir` | Output directory |

### Output Files

| File | Description |
|------|-------------|
| `*.gbf` | GenBank format annotation file |
| `*.gff` | GFF3 format annotation file (with FASTA sequence) |
| `*.CDS.fasta` | Coding sequences |
| `*.Protein.fasta` | Protein sequences |
| `*.tRNA.fasta` | tRNA sequences |
| `*.rRNA.fasta` | rRNA sequences |
| `*_image*.png/jpg` | Circular genome maps |
| `07.Report/*.log` | Analysis reports |

## System Requirements

- Linux operating system
- Apptainer >= 1.0 or Singularity >= 3.0
- At least 4GB RAM
- At least 10GB disk space

## Example
```bash
# Annotate a mitochondrial genome
apptainer exec --bind $(pwd):$(pwd) PMGA.sif \
    /apps/mgavas/bin/mgavas_m \
    -pid Arabidopsis \
    -in Arabidopsis_thaliana_mt.fasta \
    -db 4 \
    -outdir output_Arabidopsis

# Check results
ls -la output_Arabidopsis/*.gbf
ls -la output_Arabidopsis/*.gff
ls -la output_Arabidopsis/*image*
```

## Citation

If you use this tool, please cite:

> MGAVAS: Plant Mitogenome Annotation, Visualization, Analysis and Submission pipeline.
> http://www.1kmpg.cn/pmga

## License

This tool is based on MGAVAS and follows the original license.

## Contact

For issues, please submit a GitHub Issue.

## Acknowledgments

- MGAVAS development team at Institute of Medicinal Plant Development
- All contributors to the dependent tools (MAKER, tRNAscan-SE, Circos, etc.)
