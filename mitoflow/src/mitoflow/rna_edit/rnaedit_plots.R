#!/usr/bin/env Rscript
# MitoFlow RNA Editing Visualization — ggplot2 + eoffice
#
# Generates 3 publication-quality plots from RNA editing results:
#   1. editing_per_gene  — Horizontal bar chart of editing sites per gene
#   2. editing_type_pie  — Pie chart of synonymous vs nonsynonymous editing
#   3. codon_position    — Bar chart of editing sites by codon position
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript rnaedit_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript rnaedit_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]")
}

tsv_path   <- args[1]
out_prefix <- args[2]
fig_width  <- if (length(args) >= 3) as.numeric(args[3]) else 10
fig_height <- if (length(args) >= 4) as.numeric(args[4]) else 7
fig_dpi    <- if (length(args) >= 5) as.numeric(args[5]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

if (nrow(df) == 0) {
  cat("No RNA editing results to plot\n")
  quit(status = 0)
}

# Ensure numeric types
df$codon_position <- as.integer(df$codon_position)

# Editing type colors
type_colors <- c(
  "synonymous"    = "#4CAF50",
  "nonsynonymous" = "#F44336"
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
# 1. Editing Sites per Gene (horizontal bar)
# ====================================================================
plot_per_gene <- function() {
  gene_counts <- df %>%
    group_by(gene) %>%
    summarise(count = n(), .groups = "drop") %>%
    arrange(count)

  gene_counts$gene <- factor(gene_counts$gene, levels = gene_counts$gene)

  # Color by whether gene has start/stop editing
  gene_has_start <- df %>%
    filter(has_start == "TRUE") %>%
    pull(gene) %>% unique()
  gene_has_stop <- df %>%
    filter(has_stop == "TRUE") %>%
    pull(gene) %>% unique()

  gene_counts$color_group <- ifelse(gene_counts$gene %in% gene_has_start, "start_codon",
                              ifelse(gene_counts$gene %in% gene_has_stop, "stop_codon", "other"))

  bar_colors <- c("start_codon" = "#e74c3c", "stop_codon" = "#3498db", "other" = "#2ecc71")

  n_genes <- nrow(gene_counts)
  h <- max(4, n_genes * 0.25)
  w <- 10

  p <- ggplot(gene_counts, aes(x = count, y = gene, fill = color_group)) +
    geom_col(color = "black", linewidth = 0.2, width = 0.7) +
    scale_fill_manual(values = bar_colors,
                      labels = c("Start creation", "Stop removal", "Other"),
                      name = "Type") +
    labs(x = "Number of Editing Sites", y = NULL,
         title = "RNA Editing Sites per Gene") +
    theme_classic(base_size = 10) +
    theme(axis.text.y = element_text(face = "italic", size = 7))

  ggsave(paste0(out_prefix, "_editing_per_gene.png"), p, width = w, height = h, dpi = fig_dpi)
  ggsave(paste0(out_prefix, "_editing_per_gene.pdf"), p, width = w, height = h)
  tryCatch(topptx(p, paste0(out_prefix, "_editing_per_gene.pptx"), width = w, height = h),
           error = function(e) warning(paste("topptx per_gene:", e$message)))
  cat("  editing_per_gene done\n")
}

# ====================================================================
# 2. Editing Type Pie (synonymous vs nonsynonymous)
# ====================================================================
plot_type_pie <- function() {
  type_counts <- df %>%
    group_by(editing_type) %>%
    summarise(count = n(), .groups = "drop")

  p <- ggplot(type_counts, aes(x = "", y = count, fill = editing_type)) +
    geom_bar(stat = "identity", width = 1, color = "white") +
    coord_polar("y", start = 0) +
    scale_fill_manual(values = type_colors, name = "Type") +
    geom_text(aes(label = paste0(round(count / sum(count) * 100, 1), "%")),
              position = position_stack(vjust = 0.5), size = 4) +
    labs(title = "Synonymous vs Nonsynonymous Editing") +
    theme_void(base_size = 12) +
    theme(
      legend.position = "right",
      panel.border = element_rect(colour = "black", fill = NA, linewidth = 0.5)
    )

  save_plot(p, "editing_type_pie", w = 6, h = 5)
}

# ====================================================================
# 3. Codon Position Distribution
# ====================================================================
plot_codon_position <- function() {
  pos_counts <- df %>%
    group_by(codon_position) %>%
    summarise(count = n(), .groups = "drop")

  pos_counts$codon_position <- factor(pos_counts$codon_position,
                                        levels = c(1, 2, 3),
                                        labels = c("Position 1", "Position 2", "Position 3"))

  p <- ggplot(pos_counts, aes(x = codon_position, y = count, fill = codon_position)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.6) +
    geom_text(aes(label = count), vjust = -0.5, size = 4) +
    scale_fill_brewer(palette = "Set2", name = "Codon Position") +
    labs(x = NULL, y = "Number of Editing Sites",
         title = "RNA Editing by Codon Position") +
    theme_classic(base_size = 12)

  save_plot(p, "codon_position", w = 6, h = 5)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating RNA editing plots with R...\n")
plot_per_gene()
plot_type_pie()
plot_codon_position()
cat("All RNA editing plots generated.\n")
