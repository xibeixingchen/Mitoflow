#!/usr/bin/env Rscript
# MitoFlow Codon Usage Visualization — ggplot2 + eoffice
#
# Generates 7 publication-quality plots from codon usage results:
#   1. rscu_heatmap      — RSCU heatmap across genes
#   2. enc_gc3s          — ENC vs GC3s with Wright's expected curve
#   3. enc_gc3s_enhanced — ENC vs GC3s with selection/mutation classification
#   4. codon_bar         — Top codons by usage + RSCU (2-panel)
#   5. aa_freq           — Amino acid frequency bar chart
#   6. pr2_bias          — PR2 parity bias scatter plot
#   7. neutrality        — GC12 vs GC3s with regression
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript codon_plots.R <gene.tsv> <rscu.tsv> <codon.tsv> <aa.tsv> <output_prefix> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 5) {
  stop("Usage: Rscript codon_plots.R <gene.tsv> <rscu.tsv> <codon.tsv> <aa.tsv> <output_prefix> [width] [height] [dpi]")
}

gene_path   <- args[1]
rscu_path   <- args[2]
codon_path  <- args[3]
aa_path     <- args[4]
out_prefix  <- args[5]
fig_width   <- if (length(args) >= 6) as.numeric(args[6]) else 10
fig_height  <- if (length(args) >= 7) as.numeric(args[7]) else 7
fig_dpi     <- if (length(args) >= 8) as.numeric(args[8]) else 300

# ---- Read data ----
gene_df  <- read.delim(gene_path,  header = TRUE, stringsAsFactors = FALSE)
rscu_df  <- read.delim(rscu_path,  header = TRUE, stringsAsFactors = FALSE)
codon_df <- read.delim(codon_path, header = TRUE, stringsAsFactors = FALSE)
aa_df    <- read.delim(aa_path,    header = TRUE, stringsAsFactors = FALSE)

# Ensure numeric types
gene_df$enc  <- as.numeric(gene_df$enc)
gene_df$gc3s <- as.numeric(gene_df$gc3s)
gene_df$gc12 <- as.numeric(gene_df$gc12)
gene_df$a3   <- as.numeric(gene_df$a3)
gene_df$t3   <- as.numeric(gene_df$t3)
gene_df$g3   <- as.numeric(gene_df$g3)
gene_df$c3   <- as.numeric(gene_df$c3)
rscu_df$rscu <- as.numeric(rscu_df$rscu)
codon_df$count <- as.numeric(codon_df$count)
codon_df$rscu  <- as.numeric(codon_df$rscu)
aa_df$frequency <- as.numeric(aa_df$frequency)

# ---- Wright's expected ENC curve ----
enc_expected <- function(gc3s) {
  ifelse(gc3s <= 0 | gc3s >= 1, 61,
         2 + gc3s + 29 / (gc3s^2 + (1 - gc3s)^2))
}

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
# 1. RSCU Heatmap
# ====================================================================
plot_rscu_heatmap <- function() {
  if (nrow(rscu_df) == 0) {
    cat("  rscu_heatmap: no data\n")
    return()
  }

  # Limit to top genes by max RSCU
  top_genes <- rscu_df %>%
    group_by(gene) %>%
    summarise(max_rscu = max(rscu, na.rm = TRUE), .groups = "drop") %>%
    arrange(desc(max_rscu)) %>%
    head(30) %>%
    pull(gene)

  df_plot <- rscu_df %>%
    filter(gene %in% top_genes) %>%
    mutate(gene = factor(gene, levels = rev(top_genes)))

  n_genes <- length(top_genes)
  n_codons <- length(unique(df_plot$codon))
  w <- max(10, n_codons * 0.3)
  h <- max(5, n_genes * 0.3)

  p <- ggplot(df_plot, aes(x = codon, y = gene, fill = rscu)) +
    geom_tile(color = "white", linewidth = 0.2) +
    scale_fill_gradientn(
      colours = c("#4575b4", "#ffffbf", "#d73027"),
      values = c(0, 0.33, 1),
      limits = c(0, 3),
      name = "RSCU"
    ) +
    labs(x = "Codon", y = "Gene",
         title = "RSCU Heatmap") +
    theme_classic(base_size = 8) +
    theme(
      axis.text.x = element_text(angle = 90, hjust = 1, vjust = 0.5, size = 6),
      axis.text.y = element_text(size = 6),
      panel.border = element_rect(colour = "black", fill = NA, linewidth = 0.5)
    )

  ggsave(paste0(out_prefix, "_rscu_heatmap.png"), p, width = w, height = h, dpi = fig_dpi)
  ggsave(paste0(out_prefix, "_rscu_heatmap.pdf"), p, width = w, height = h)
  tryCatch(topptx(p, paste0(out_prefix, "_rscu_heatmap.pptx"), width = w, height = h),
           error = function(e) warning(paste("topptx rscu_heatmap:", e$message)))
  cat("  rscu_heatmap done\n")
}

# ====================================================================
# 2. ENC vs GC3s
# ====================================================================
plot_enc_gc3s <- function() {
  if (nrow(gene_df) == 0) {
    cat("  enc_gc3s: no data\n")
    return()
  }

  # Expected curve
  gc3s_range <- seq(0.01, 0.99, length.out = 200)
  expected_df <- data.frame(gc3s = gc3s_range, enc_exp = enc_expected(gc3s_range))

  # Mean values
  mean_enc  <- mean(gene_df$enc, na.rm = TRUE)
  mean_gc3s <- mean(gene_df$gc3s, na.rm = TRUE)

  p <- ggplot(gene_df, aes(x = gc3s, y = enc)) +
    geom_line(data = expected_df, aes(x = gc3s, y = enc_exp),
              color = "black", linetype = "dashed", linewidth = 0.8) +
    geom_point(color = "#2196F3", alpha = 0.6, size = 2, shape = 16) +
    geom_point(data = data.frame(x = mean_gc3s, y = mean_enc),
               aes(x = x, y = y), color = "red", size = 3, shape = 8) +
    annotate("text", x = mean_gc3s + 0.05, y = mean_enc + 1,
             label = sprintf("Mean (ENC=%.1f, GC3s=%.3f)", mean_enc, mean_gc3s),
             size = 3, hjust = 0) +
    annotate("text", x = 0.8, y = enc_expected(0.8) + 1,
             label = "Expected (Wright 1990)", size = 3) +
    labs(x = "GC3s", y = "ENC (Effective Number of Codons)",
         title = "ENC-plot: ENC vs GC3s") +
    xlim(0, 1) + ylim(20, 61) +
    theme_classic(base_size = 11)

  save_plot(p, "enc_gc3s", w = 8, h = 6)
}

# ====================================================================
# 3. ENC vs GC3s (Enhanced with selection classification)
# ====================================================================
plot_enc_gc3s_enhanced <- function() {
  if (nrow(gene_df) == 0) {
    cat("  enc_gc3s_enhanced: no data\n")
    return()
  }

  threshold <- 10

  gene_df_class <- gene_df %>%
    mutate(
      enc_exp = enc_expected(gc3s),
      distance = enc_exp - enc,
      class = ifelse(distance > threshold, "Selection-driven", "Mutation-driven")
    )

  n_selected <- sum(gene_df_class$class == "Selection-driven")

  expected_df <- data.frame(gc3s = seq(0.01, 0.99, length.out = 200))
  expected_df$enc_exp <- enc_expected(expected_df$gc3s)

  p <- ggplot(gene_df_class, aes(x = gc3s, y = enc, color = class)) +
    geom_line(data = expected_df, aes(x = gc3s, y = enc_exp),
              color = "black", linetype = "dashed", linewidth = 0.8, inherit.aes = FALSE) +
    geom_point(size = 2, alpha = 0.7) +
    scale_color_manual(
      values = c("Mutation-driven" = "#2196F3", "Selection-driven" = "#F44336"),
      name = "Class"
    ) +
    geom_point(data = data.frame(x = mean(gene_df$gc3s), y = mean(gene_df$enc)),
               aes(x = x, y = y), color = "red", size = 3, shape = 8, inherit.aes = FALSE) +
    labs(x = "GC3s", y = "ENC",
         title = "ENC-plot: Selection vs Mutation Bias") +
    xlim(0, 1) + ylim(20, 61) +
    theme_classic(base_size = 11)

  save_plot(p, "enc_gc3s_enhanced", w = 8, h = 6)
}

# ====================================================================
# 4. Codon Usage Bar (2-panel: count + RSCU)
# ====================================================================
plot_codon_bar <- function() {
  if (nrow(codon_df) == 0) {
    cat("  codon_bar: no data\n")
    return()
  }

  top20 <- codon_df %>% arrange(desc(count)) %>% head(20)
  top20$label <- paste0(top20$codon, "\n(", top20$aa, ")")
  top20$label <- factor(top20$label, levels = top20$label)

  # Color by RSCU bias
  top20 <- top20 %>%
    mutate(bias = ifelse(rscu > 1.5, "Preferred",
                   ifelse(rscu < 0.5, "Avoided", "Neutral")))

  bias_colors <- c("Preferred" = "#4CAF50", "Avoided" = "#F44336", "Neutral" = "#2196F3")

  # Panel 1: Counts
  p1 <- ggplot(top20, aes(x = label, y = count, fill = bias)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.2, width = 0.7) +
    scale_fill_manual(values = bias_colors, name = "Bias") +
    labs(x = NULL, y = "Count", title = "Top 20 Codons by Usage") +
    theme_classic(base_size = 9) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1, size = 7))

  # Panel 2: RSCU
  p2 <- ggplot(top20, aes(x = label, y = rscu, fill = bias)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.2, width = 0.7) +
    geom_hline(yintercept = 1.0, color = "black", linetype = "dashed", linewidth = 0.6) +
    scale_fill_manual(values = bias_colors, name = "Bias") +
    labs(x = NULL, y = "RSCU", title = "RSCU Values") +
    theme_classic(base_size = 9) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1, size = 7))

  library(gridExtra)
  p <- arrangeGrob(p1, p2, ncol = 2)

  w <- 12; h <- 5
  ggsave(paste0(out_prefix, "_codon_bar.png"), p, width = w, height = h, dpi = fig_dpi)
  ggsave(paste0(out_prefix, "_codon_bar.pdf"), p, width = w, height = h)
  tryCatch(topptx(p, paste0(out_prefix, "_codon_bar.pptx"), width = w, height = h),
           error = function(e) warning(paste("topptx codon_bar:", e$message)))
  cat("  codon_bar done\n")
}

# ====================================================================
# 5. Amino Acid Frequency
# ====================================================================
plot_aa_freq <- function() {
  if (nrow(aa_df) == 0) {
    cat("  aa_freq: no data\n")
    return()
  }

  aa_df$aa <- factor(aa_df$aa, levels = aa_df$aa[order(aa_df$frequency, decreasing = TRUE)])

  p <- ggplot(aa_df, aes(x = aa, y = frequency)) +
    geom_bar(stat = "identity", fill = "#5C6BC0", color = "black", linewidth = 0.2, width = 0.7) +
    labs(x = "Amino Acid", y = "Frequency (%)",
         title = "Amino Acid Frequency") +
    theme_classic(base_size = 11)

  save_plot(p, "aa_freq", w = 10, h = 5)
}

# ====================================================================
# 6. PR2 Bias Plot
# ====================================================================
plot_pr2_bias <- function() {
  if (nrow(gene_df) == 0) {
    cat("  pr2_bias: no data\n")
    return()
  }

  pr2_df <- gene_df %>%
    mutate(
      at_bias = ifelse((a3 + t3) > 0, a3 / (a3 + t3), 0.5),
      gc_bias = ifelse((g3 + c3) > 0, g3 / (g3 + c3), 0.5)
    )

  p <- ggplot(pr2_df, aes(x = at_bias, y = gc_bias)) +
    geom_point(color = "#2196F3", alpha = 0.6, size = 2, shape = 16) +
    geom_hline(yintercept = 0.5, color = "gray", linetype = "dashed", linewidth = 0.6) +
    geom_vline(xintercept = 0.5, color = "gray", linetype = "dashed", linewidth = 0.6) +
    annotate("text", x = 0.25, y = 0.75, label = "G/A bias", size = 3, color = "gray") +
    annotate("text", x = 0.75, y = 0.75, label = "G/T bias", size = 3, color = "gray") +
    annotate("text", x = 0.25, y = 0.25, label = "C/A bias", size = 3, color = "gray") +
    annotate("text", x = 0.75, y = 0.25, label = "C/T bias", size = 3, color = "gray") +
    labs(x = expression(A[3] / (A[3] + T[3])),
         y = expression(G[3] / (G[3] + C[3])),
         title = "PR2 Bias Plot") +
    xlim(0, 1) + ylim(0, 1) +
    theme_classic(base_size = 11)

  save_plot(p, "pr2_bias", w = 7, h = 7)
}

# ====================================================================
# 7. Neutrality Plot (GC12 vs GC3s)
# ====================================================================
plot_neutrality <- function() {
  if (nrow(gene_df) == 0) {
    cat("  neutrality: no data\n")
    return()
  }

  p <- ggplot(gene_df, aes(x = gc3s, y = gc12)) +
    geom_point(color = "#2196F3", alpha = 0.6, size = 2, shape = 16) +
    geom_abline(intercept = 0, slope = 1, linetype = "dashed", color = "black", linewidth = 0.8) +
    labs(x = "GC3s", y = "GC12",
         title = "Neutrality Plot: GC12 vs GC3s") +
    xlim(0, 1) + ylim(0, 1) +
    theme_classic(base_size = 11)

  # Add regression line if enough points
  if (nrow(gene_df) > 2) {
    fit <- lm(gc12 ~ gc3s, data = gene_df)
    slope <- coef(fit)[2]
    p <- p + geom_smooth(method = "lm", se = FALSE, color = "red", linewidth = 0.8) +
      annotate("text", x = 0.9, y = 0.1,
               label = sprintf("slope = %.3f", slope),
               size = 3.5, hjust = 1)
  }

  save_plot(p, "neutrality", w = 7, h = 7)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating Codon Usage plots with R...\n")
plot_rscu_heatmap()
plot_enc_gc3s()
plot_enc_gc3s_enhanced()
plot_codon_bar()
plot_aa_freq()
plot_pr2_bias()
plot_neutrality()
cat("All Codon Usage plots generated.\n")
