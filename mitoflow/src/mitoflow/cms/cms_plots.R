#!/usr/bin/env Rscript
# MitoFlow CMS Visualization — ggplot2 + eoffice
#
# Generates publication-quality plots from CMS candidate prediction results:
#   1. cms_scores        — Stacked horizontal bar chart of score breakdown
#   2. cms_heatmap       — Heatmap of candidates x scoring dimensions
#   3. cms_genome_context — Linear genome map with CMS candidates marked
#   4. cms_confidence    — Donut chart of confidence level distribution
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript cms_plots.R <input.tsv> <output_prefix> [genome_length] [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript cms_plots.R <input.tsv> <output_prefix> [genome_length] [width] [height] [dpi]")
}

tsv_path     <- args[1]
out_prefix   <- args[2]
genome_len   <- if (length(args) >= 3) as.numeric(args[3]) else 0
fig_width    <- if (length(args) >= 4) as.numeric(args[4]) else 10
fig_height   <- if (length(args) >= 5) as.numeric(args[5]) else 7
fig_dpi      <- if (length(args) >= 6) as.numeric(args[6]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

if (nrow(df) == 0) {
  cat("No CMS candidates to plot\n")
  quit(status = 0)
}

# Ensure numeric types
df$chimera_score  <- as.numeric(df$chimera_score)
df$tm_score       <- as.numeric(df$tm_score)
df$homolog_score  <- as.numeric(df$homolog_score)
df$context_score  <- as.numeric(df$context_score)
df$length_score   <- as.numeric(df$length_score)
df$total_score    <- as.numeric(df$total_score)
df$start          <- as.numeric(df$start)
df$end            <- as.numeric(df$end)
df$length_aa      <- as.numeric(df$length_aa)
df$n_tm_domains   <- as.numeric(df$n_tm_domains)

# Colors
score_colors <- c(
  "chimera"  = "#e74c3c",
  "tm"       = "#3498db",
  "homolog"  = "#2ecc71",
  "context"  = "#f39c12",
  "length"   = "#9b59b6"
)

conf_colors <- c(
  "High"   = "#e74c3c",
  "Medium" = "#f39c12",
  "Low"    = "#95a5a6"
)

# Weights
weights <- c(chimera = 0.30, tm = 0.25, homolog = 0.20,
             context = 0.15, length = 0.10)

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
# 1. CMS Score Breakdown (stacked horizontal bar)
# ====================================================================
plot_scores <- function() {
  # Reshape to long format
  df_long <- df %>%
    select(orf_id, chimera_score, tm_score, homolog_score,
           context_score, length_score, total_score, confidence) %>%
    pivot_longer(
      cols = c(chimera_score, tm_score, homolog_score,
               context_score, length_score),
      names_to = "dimension",
      values_to = "score"
    ) %>%
    mutate(
      dimension = sub("_score$", "", dimension),
      weight = weights[dimension],
      weighted_score = score * weight,
      orf_id = factor(orf_id, levels = rev(unique(df$orf_id)))
    )

  p <- ggplot(df_long, aes(x = orf_id, y = weighted_score, fill = dimension)) +
    geom_bar(stat = "identity", color = "white", linewidth = 0.3, width = 0.7) +
    coord_flip() +
    scale_fill_manual(values = score_colors, name = "Dimension") +
    labs(x = NULL, y = "Weighted Score",
         title = "CMS Candidate Score Breakdown") +
    theme_classic(base_size = 12)

  # Add confidence markers
  conf_df <- df %>%
    mutate(orf_id = factor(orf_id, levels = rev(unique(df$orf_id)))) %>%
    select(orf_id, total_score, confidence)

  p <- p +
    geom_point(data = conf_df, aes(x = orf_id, y = total_score,
                                    fill = NULL, shape = confidence),
               size = 3, inherit.aes = FALSE) +
    scale_shape_manual(values = c(High = 17, Medium = 15, Low = 16),
                       name = "Confidence") +
    guides(fill = guide_legend(order = 1), shape = guide_legend(order = 2))

  n_cand <- nrow(df)
  w <- max(10, n_cand * 0.8)
  h <- max(5, n_cand * 0.4 + 1.5)

  save_plot(p, "cms_scores", w = w, h = h)
}

# ====================================================================
# 2. CMS Heatmap (candidates x dimensions)
# ====================================================================
plot_heatmap <- function() {
  dims <- c("chimera_score", "tm_score", "homolog_score",
            "context_score", "length_score")
  dim_labels <- c("Chimera", "TM", "Homolog", "Context", "Length")

  df_heat <- df %>%
    select(all_of(dims)) %>%
    as.matrix()
  rownames(df_heat) <- df$orf_id
  colnames(df_heat) <- dim_labels

  df_heat_long <- as.data.frame(as.table(df_heat)) %>%
    rename(orf_id = Var1, Dimension = Var2, Score = Freq) %>%
    mutate(
      orf_id = factor(orf_id, levels = rev(unique(df$orf_id))),
      Dimension = factor(Dimension, levels = dim_labels),
      Score = as.numeric(Score)
    )

  p <- ggplot(df_heat_long, aes(x = Dimension, y = orf_id, fill = Score)) +
    geom_tile(color = "white", linewidth = 0.3) +
    geom_text(aes(label = round(Score, 0)), size = 3,
              color = ifelse(df_heat_long$Score > 60, "white", "black")) +
    scale_fill_gradient(low = "#FFFFCC", high = "#B10026",
                        name = "Score") +
    labs(x = NULL, y = NULL,
         title = "CMS Candidate Scoring Heatmap") +
    theme_classic(base_size = 11) +
    theme(axis.text.y = element_text(size = 7),
          axis.text.x = element_text(size = 9))

  n_cand <- nrow(df)
  w <- max(6, 5 * 1.2 + 2)
  h <- max(4, n_cand * 0.35 + 1.5)

  save_plot(p, "cms_heatmap", w = w, h = h)
}

# ====================================================================
# 3. CMS Genome Context (linear map with candidates)
# ====================================================================
plot_genome_context <- function() {
  if (genome_len <= 0) {
    cat("  cms_genome_context skipped: genome_length not provided\n")
    return()
  }

  mb <- 1000000
  df$candidate_mid <- (df$start + df$end) / 2
  df$confidence <- factor(df$confidence, levels = c("High", "Medium", "Low"))

  # Genome backbone ticks
  tick_step <- max(1, floor(genome_len / mb / 10)) * mb
  ticks <- data.frame(pos = seq(0, genome_len, by = tick_step))

  p <- ggplot(df) +
    # Genome backbone
    geom_segment(aes(x = 0, xend = genome_len, y = 0, yend = 0),
                 color = "#2c3e50", linewidth = 2) +
    # Tick marks
    geom_segment(data = ticks, aes(x = pos, xend = pos, y = -0.1, yend = 0.1),
                 color = "#2c3e50", linewidth = 0.5) +
    geom_text(data = ticks, aes(x = pos, y = -0.2, label = paste0(round(pos / mb, 1), " Mb")),
              size = 3, vjust = 1) +
    # Candidate points
    geom_point(aes(x = candidate_mid, y = 1, color = confidence),
               size = 4, alpha = 0.85) +
    # Connecting lines
    geom_segment(aes(x = candidate_mid, xend = candidate_mid,
                     y = 0, yend = 0.9, color = confidence),
                 linewidth = 0.4, alpha = 0.5) +
    # Labels
    geom_text(aes(x = candidate_mid, y = 1.2, label = orf_id),
              size = 2.5, angle = 30, hjust = 0, vjust = 0) +
    scale_color_manual(values = conf_colors, name = "Confidence") +
    labs(x = "Genome Position (bp)", y = NULL,
         title = paste0("CMS Candidates on Genome (", format(genome_len, big.mark = ","), " bp)")) +
    theme_classic(base_size = 11) +
    theme(axis.line.y = element_blank(),
          axis.text.y = element_blank(),
          axis.ticks.y = element_blank())

  save_plot(p, "cms_genome_context", w = 14, h = 5)
}

# ====================================================================
# 4. CMS Confidence Distribution (donut chart)
# ====================================================================
plot_confidence <- function() {
  conf_df <- df %>%
    group_by(confidence) %>%
    summarise(Count = n(), .groups = "drop") %>%
    mutate(
      confidence = factor(confidence, levels = c("High", "Medium", "Low")),
      fraction = Count / sum(Count),
      ymax = cumsum(fraction),
      ymin = c(0, head(cumsum(fraction), -1)),
      label_pos = (ymin + ymax) / 2,
      label = paste0(confidence, "\n", Count, " (", scales::percent(fraction), ")")
    )

  p <- ggplot(conf_df) +
    geom_rect(aes(ymax = ymax, ymin = ymin, xmax = 4, xmin = 3, fill = confidence)) +
    geom_text(aes(x = 3.5, y = label_pos, label = label),
              size = 4, fontface = "bold") +
    scale_fill_manual(values = conf_colors, name = "Confidence") +
    coord_polar(theta = "y") +
    xlim(c(0, 5)) +
    labs(title = "CMS Candidate Confidence Distribution") +
    theme_void(base_size = 12) +
    theme(legend.position = "none")

  save_plot(p, "cms_confidence", w = 7, h = 7)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating CMS plots with R...\n")
plot_scores()
plot_heatmap()
plot_genome_context()
plot_confidence()
cat("All CMS plots generated.\n")
