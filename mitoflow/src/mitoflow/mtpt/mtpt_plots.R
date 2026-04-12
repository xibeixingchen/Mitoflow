#!/usr/bin/env Rscript
# MitoFlow MTPT Visualization — ggplot2 + eoffice
#
# Generates 4 publication-quality plots from MTPT detection results:
#   1. mtpt_barplot      — Bar plot of MTPT count by category
#   2. mtpt_identity      — Histogram of MTPT identity distribution
#   3. mtpt_mito_map      — Dot plot of MTPT positions on mitochondrial genome
#   4. mtpt_gene_coverage — Bar chart of cp genes found in MTPTs
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript mtpt_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript mtpt_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]")
}

tsv_path   <- args[1]
out_prefix <- args[2]
fig_width  <- if (length(args) >= 3) as.numeric(args[3]) else 10
fig_height <- if (length(args) >= 4) as.numeric(args[4]) else 7
fig_dpi    <- if (length(args) >= 5) as.numeric(args[5]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

if (nrow(df) == 0) {
  cat("No MTPT results to plot\n")
  quit(status = 0)
}

df$Identity  <- as.numeric(df$Identity)
df$Length    <- as.numeric(df$Length)
df$MitoStart <- as.numeric(df$MitoStart)
df$MitoEnd   <- as.numeric(df$MitoEnd)
df$CpStart   <- as.numeric(df$CpStart)
df$CpEnd     <- as.numeric(df$CpEnd)

# Category colors
cat_colors <- c(
  "intact"     = "#4CAF50",
  "degenerate" = "#FF9800",
  "fragment"   = "#2196F3",
  "ancient"    = "#9E9E9E"
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
# 1. MTPT Category Bar Plot
# ====================================================================
plot_barplot <- function() {
  cat_counts <- df %>%
    group_by(Category) %>%
    summarise(Count = n(), .groups = "drop")

  cat_counts$Category <- factor(cat_counts$Category,
                                 levels = c("intact", "degenerate", "fragment", "ancient"))

  p <- ggplot(cat_counts, aes(x = Category, y = Count, fill = Category)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.6) +
    geom_text(aes(label = Count), vjust = -0.5, size = 4) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = NULL, y = "MTPT Count",
         title = "MTPT Distribution by Category") +
    theme_classic(base_size = 12)

  save_plot(p, "mtpt_barplot", w = 6, h = 5)
}

# ====================================================================
# 2. MTPT Identity Distribution
# ====================================================================
plot_identity <- function() {
  p <- ggplot(df, aes(x = Identity, fill = Category)) +
    geom_histogram(bins = 30, color = "black", linewidth = 0.2, alpha = 0.8) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = "Identity (%)", y = "Count",
         title = "MTPT Identity Distribution") +
    theme_classic(base_size = 12)

  save_plot(p, "mtpt_identity", w = 7, h = 5)
}

# ====================================================================
# 3. MTPT Mito Coverage Map
# ====================================================================
plot_mito_map <- function() {
  p <- ggplot(df, aes(x = (MitoStart + MitoEnd) / 2, y = Identity,
                       color = Category, size = Length)) +
    geom_point(alpha = 0.7) +
    scale_color_manual(values = cat_colors, name = "Category") +
    scale_size_continuous(name = "Length (bp)", range = c(1, 6)) +
    labs(x = "Mitochondrial Position (bp)", y = "Identity (%)",
         title = "MTPT Coverage on Mitochondrial Genome") +
    theme_classic(base_size = 11) +
    theme(legend.position = "right")

  save_plot(p, "mtpt_mito_map", w = 9, h = 5)
}

# ====================================================================
# 4. MTPT cp Gene Coverage
# ====================================================================
plot_gene_coverage <- function() {
  # Parse gene lists
  all_genes <- unlist(strsplit(paste(df$CpGenes, collapse = ","), ","))
  all_genes <- trimws(all_genes[all_genes != "none" & all_genes != ""])

  if (length(all_genes) == 0) {
    cat("  mtpt_gene_coverage: no cp genes found, skipping\n")
    return()
  }

  gene_counts <- as.data.frame(table(all_genes), stringsAsFactors = FALSE)
  names(gene_counts) <- c("Gene", "Count")
  gene_counts <- gene_counts %>% arrange(desc(Count))
  gene_counts$Gene <- factor(gene_counts$Gene, levels = gene_counts$Gene)

  n_genes <- nrow(gene_counts)
  h <- max(5, n_genes * 0.3)

  p <- ggplot(gene_counts, aes(x = Gene, y = Count)) +
    geom_bar(stat = "identity", fill="#4CAF50", color = "black", linewidth = 0.2, width = 0.7) +
    geom_text(aes(label = Count), vjust = -0.3, size = 3) +
    labs(x = NULL, y = "MTPT Regions Covering Gene",
         title = "Chloroplast Gene Coverage in MTPTs") +
    theme_classic(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1))

  save_plot(p, "mtpt_gene_coverage", w = max(8, n_genes * 0.4), h = h)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating MTPT plots with R...\n")
plot_barplot()
plot_identity()
plot_mito_map()
plot_gene_coverage()
cat("All MTPT plots generated.\n")
