#!/usr/bin/env Rscript
# MitoFlow Pi (Nucleotide Diversity) Visualization — ggplot2 + eoffice
#
# Generates 3 publication-quality plots from Pi results:
#   1. pi_bar          — Horizontal bar chart of Pi by region (CDS/IGS colored, hotspots marked)
#   2. pi_distribution — Histogram of Pi values
#   3. pi_comparison   — Grouped bar chart comparing Pi across species pairs
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript pi_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript pi_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]")
}

tsv_path   <- args[1]
out_prefix <- args[2]
fig_width  <- if (length(args) >= 3) as.numeric(args[3]) else 10
fig_height <- if (length(args) >= 4) as.numeric(args[4]) else 7
fig_dpi    <- if (length(args) >= 5) as.numeric(args[5]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

if (nrow(df) == 0) {
  cat("No Pi results to plot\n")
  quit(status = 0)
}

# Ensure numeric types
df$pi_value <- as.numeric(df$pi_value)

# Region type colors
type_colors <- c(
  "CDS"      = "#2196F3",
  "IGS"      = "#FF9800",
  "hotspot"  = "#F44336"
)

# ---- Helper: save plot in 3 formats ----
save_plot <- function(p, name, w = fig_width, h = fig_height) {
  png_path  <- paste0(out_prefix, "_", name, ".png")
  pdf_path  <- paste0(out_prefix, "_", name, ".pdf")
  pptx_path <- paste0(out_prefix, "_", name, ".pptx")

  ggsave(png_path, p, width = w, height = h, dpi = fig_dpi)
  ggsave(pdf_path, p, width = w, height = h)

  tryCatch({
    topptx(p, pptx_path, width = w, height = h)
  }, error = function(e) {
    warning(paste("topptx failed for", name, ":", e$message))
  })

  cat(paste0("  ", name, ": ", png_path, ", ", pdf_path, ", ", pptx_path, "\n"))
}

# ====================================================================
# 1. Pi Bar Chart (horizontal, sorted by Pi value)
# ====================================================================
plot_pi_bar <- function() {
  hotspot_threshold <- 0.01

  df_sorted <- df %>%
    arrange(desc(pi_value)) %>%
    mutate(region = factor(region, levels = region))

  # Color: hotspot=red, CDS=blue, IGS=orange
  df_sorted$color_group <- ifelse(df_sorted$is_hotspot == "TRUE", "hotspot", df_sorted$region_type)

  n_regions <- nrow(df_sorted)
  h <- max(4, n_regions * 0.25)
  w <- 10

  p <- ggplot(df_sorted, aes(x = pi_value, y = region, fill = color_group)) +
    geom_col(color = "black", linewidth = 0.2, width = 0.7) +
    geom_vline(xintercept = hotspot_threshold, color = "red",
               linetype = "dashed", linewidth = 0.6) +
    scale_fill_manual(values = type_colors,
                      labels = c("CDS", "Hotspot", "IGS"),
                      name = "Type") +
    labs(x = "Nucleotide Diversity (Pi)", y = NULL,
         title = "Nucleotide Diversity across Regions") +
    theme_classic(base_size = 10) +
    theme(
      axis.text.y = element_text(face = "italic", size = 7),
      legend.position = "right"
    )

  ggsave(paste0(out_prefix, "_pi_bar.png"), p, width = w, height = h, dpi = fig_dpi)
  ggsave(paste0(out_prefix, "_pi_bar.pdf"), p, width = w, height = h)
  tryCatch(topptx(p, paste0(out_prefix, "_pi_bar.pptx"), width = w, height = h),
           error = function(e) warning(paste("topptx pi_bar:", e$message)))
  cat("  pi_bar done\n")
}

# ====================================================================
# 2. Pi Distribution Histogram
# ====================================================================
plot_pi_distribution <- function() {
  p <- ggplot(df, aes(x = pi_value, fill = region_type)) +
    geom_histogram(bins = 30, color = "black", linewidth = 0.2, alpha = 0.8) +
    geom_vline(xintercept = 0.01, color = "red", linetype = "dashed", linewidth = 0.6) +
    scale_fill_manual(values = c("CDS" = "#2196F3", "IGS" = "#FF9800"), name = "Region Type") +
    labs(x = "Nucleotide Diversity (Pi)", y = "Count",
         title = "Distribution of Pi Values") +
    theme_classic(base_size = 12)

  save_plot(p, "pi_distribution", w = 7, h = 5)
}

# ====================================================================
# 3. Pi Comparison across Species Pairs (if species column present)
# ====================================================================
plot_pi_comparison <- function() {
  if (!"species" %in% colnames(df) || length(unique(df$species)) <= 1) {
    cat("  pi_comparison: skipped (single species or no species column)\n")
    return()
  }

  # Summarise mean Pi by species and region type
  df_summary <- df %>%
    group_by(species, region_type) %>%
    summarise(mean_pi = mean(pi_value, na.rm = TRUE), .groups = "drop")

  p <- ggplot(df_summary, aes(x = species, y = mean_pi, fill = region_type)) +
    geom_bar(stat = "identity", position = "dodge", color = "black", linewidth = 0.2) +
    scale_fill_manual(values = c("CDS" = "#2196F3", "IGS" = "#FF9800"), name = "Region Type") +
    labs(x = NULL, y = "Mean Pi",
         title = "Mean Nucleotide Diversity by Species Pair") +
    theme_classic(base_size = 11) +
    theme(axis.text.x = element_text(angle = 30, hjust = 1))

  save_plot(p, "pi_comparison", w = 8, h = 5)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating Pi plots with R...\n")
plot_pi_bar()
plot_pi_distribution()
plot_pi_comparison()
cat("All Pi plots generated.\n")
