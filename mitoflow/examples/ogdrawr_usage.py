#!/usr/bin/env python3
"""
OGDrawR Integration Example for MitoFlow

This example demonstrates how to use the OGDrawR R package for
circular mitochondrial genome visualization within the MitoFlow pipeline.

Requirements:
    - R with OGDrawR package installed:
      Rscript -e "remotes::install_github('xibeixingchen/OGDrawR')"
    
    For headless environments (servers without X11):
    - Output will automatically be converted to PDF format

Usage:
    python ogdrawr_usage.py <genbank_file> [output_file]

Examples:
    # Basic usage (auto-detects output format from extension)
    python ogdrawr_usage.py genome.gb genome_map.png
    
    # In headless environments, use PDF format
    python ogdrawr_usage.py genome.gb genome_map.pdf
    
    # With organism name
    python ogdrawr_usage.py genome.gb genome_map.pdf "Arabidopsis thaliana"
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.viz import draw_ogdraw_genome, check_ogdrawr_available


def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    genbank_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "genome_map.pdf"
    organism = sys.argv[3] if len(sys.argv) > 3 else ""
    
    # Check if OGDrawR is available
    if not check_ogdrawr_available():
        print("Warning: OGDrawR R package not available.")
        print("Will use Python pycirclize fallback instead.")
        print("\nTo install OGDrawR:")
        print("  Rscript -e \"remotes::install_github('xibeixingchen/OGDrawR')\"")
        print()
    
    # Generate visualization
    print(f"Input: {genbank_file}")
    print(f"Output: {output_file}")
    if organism:
        print(f"Organism: {organism}")
    
    try:
        result = draw_ogdraw_genome(
            genbank_path=genbank_file,
            output_path=output_file,
            organism=organism,
            use_ogdrawr=True,  # Try to use OGDrawR, fallback to pycirclize if unavailable
        )
        print(f"\nSuccess! Visualization saved to: {result}")
        
        # Check if output was converted to PDF (headless environment)
        if result.suffix.lower() == ".pdf" and output_file.lower().endswith(".png"):
            print("\nNote: Output was converted to PDF due to headless environment.")
            print("      PNG requires X11 which is not available on this system.")
            
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
