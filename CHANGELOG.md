# Changelog

## v1.0 (2026-01-10)

### Fixed

- Fixed GFF file not being generated when IR region merge fails
- Fixed `_merged.fas` and `_merged_stat.txt` files missing for single sequence input
- Fixed `merged_stat.txt` file format error (removed header, correct 3-column format)
- Fixed GenBank LOCUS line format overflow caused by long species names

### Added

- Added complete Perl module dependencies for Circos and GeneMap plotting
- Added multiple fallback file copy mechanisms for fault tolerance

### Improved

- Optimized error output, suppressed unnecessary warning messages
- Improved file organization process
