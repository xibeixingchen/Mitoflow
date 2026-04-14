#!/bin/bash
# Run MitoFlow on gold standard species

INPUT_DIR="data/gold_standard/fasta"
OUTPUT_DIR="results/round1/mitoflow_output"
THREADS=4

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Get list of species
species=$(ls "$INPUT_DIR"/*.fasta | xargs -I{} basename {} .fasta | sort)

echo "=== MitoFlow Gold Standard Batch Run ==="
echo "Started: $(date)"
echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Threads: $THREADS"
echo ""

count=0
total=$(ls "$INPUT_DIR"/*.fasta | wc -l)

for sp in $species; do
    input_file="${INPUT_DIR}/${sp}.fasta"
    output_dir="${OUTPUT_DIR}/${sp}"

    if [ -f "$input_file" ]; then
        count=$((count + 1))
        echo "--- [$count/$total] Processing $sp ---"

        # Run MitoFlow annotation
        mitoflow annotate -i "$input_file" -o "$output_dir" --name "$sp" --threads $THREADS

        if [ -d "$output_dir/genbank" ]; then
            echo "✓ Success: $sp"
        else
            echo "✗ Failed: $sp"
        fi
    else
        echo "Warning: Input file not found for $sp"
    fi
done

echo ""
echo "=== Batch Run Complete ==="
echo "Finished: $(date)"
echo "Processed: $count/$total species"