#!/usr/bin/env Rscript
# OGDrawR wrapper for MitoFlow pipeline.
#
# Usage:
#     Rscript ogdrawr_wrapper.R <genbank_file> <output_file> [genome_name]
#
# Args:
#     genbank_file: Path to input GenBank file
#     output_file: Path to output image (.png/.pdf/.tiff/.svg)
#     genome_name: Optional genome name for center label

# Detect if running in headless environment (no X11)
is_headless <- function() {
  caps <- capabilities()
  if (!is.null(caps["X11"]) && caps["X11"] == FALSE) {
    return(TRUE)
  }
  if (Sys.info()["sysname"] == "Linux" && nchar(Sys.getenv("DISPLAY")) == 0) {
    return(TRUE)
  }
  return(FALSE)
}

# Parse command line arguments
args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 2) {
    cat("Usage: Rscript ogdrawr_wrapper.R <genbank_file> <output_file> [genome_name]\n")
    quit(status = 1)
}

genbank_file <- args[1]
output_file <- args[2]
genome_name <- ifelse(length(args) >= 3, args[3], "Mitochondrial Genome")

output_ext <- tools::file_ext(tolower(output_file))
headless <- is_headless()

# Load required libraries
if (!requireNamespace("OGDrawR", quietly = TRUE)) {
    cat("Error: OGDrawR package not found. Please install it first.\n")
    cat("Run: remotes::install_github('xibeichens/OGDrawR')\n")
    quit(status = 1)
}

library(OGDrawR)

# Check if input file exists
if (!file.exists(genbank_file)) {
    stop(sprintf("Input file not found: %s", genbank_file))
}

# Parse GenBank file
cat(sprintf("Parsing GenBank file: %s\n", genbank_file))
parsed <- parse_genbank(genbank_file)

# Draw genome map
cat(sprintf("Generating visualization: %s\n", output_file))

# In headless environments, OGDrawR's internal png() call fails without X11.
# Solution: open the device ourselves with type="cairo", then call
# draw_mito_map with output_file=NULL so it doesn't try to open one.
preopen_device <- FALSE

if (headless && output_ext == "png") {
  cat("Headless environment: opening PNG device with cairo backend.\n")
  png(output_file, width = 12, height = 12, units = "in", res = 600, type = "cairo")
  preopen_device <- TRUE
} else if (headless && output_ext == "tiff") {
  cat("Headless environment: opening TIFF device with cairo backend.\n")
  tiff(output_file, width = 12, height = 12, units = "in", res = 600,
       compression = "lzw", type = "cairo")
  preopen_device <- TRUE
}

tryCatch({
  if (preopen_device) {
    # OGDrawR with output_file=NULL skips device creation
    draw_mito_map(
        parsed = parsed,
        genome_name = genome_name,
        output_file = NULL,
        w = 12,
        h = 12,
        res = 600
    )
    dev.off()
  } else {
    draw_mito_map(
        parsed = parsed,
        genome_name = genome_name,
        output_file = output_file,
        w = 12,
        h = 12,
        res = 600
    )
  }

  cat(sprintf("Successfully created: %s\n", output_file))
}, error = function(e) {
  if (preopen_device && dev.cur() > 1) dev.off()
  cat(sprintf("Error: %s\n", e$message))
  quit(status = 1)
})

quit(status = 0)
