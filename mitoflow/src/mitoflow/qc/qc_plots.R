#!/usr/bin/env Rscript
# MitoFlow QC Visualization — ggplot2 + eoffice
#
# Generates 3 publication-quality plots from QC results:
#   1. qc_radar    — Radar/spider chart of 5 QC dimensions
#   2. qc_gauge    — Overall score gauge chart with grade
#   3. qc_summary  — Bar chart of dimension scores with thresholds
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript qc_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript qc_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]")
}

tsv_path   <- args[1]
out_prefix <- args[2]
fig_width  <- if (length(args) >= 3) as.numeric(args[3]) else 10
fig_height <- if (length(args) >= 4) as.numeric(args[4]) else 7
fig_dpi    <- if (length(args) >= 5) as.numeric(args[5]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

# Extract scores
dimensions <- c("Completeness", "Contiguity", "Correctness", "Contamination", "Structure")
scores <- c(
  df$completeness_score[1],
  df$contiguity_score[1],
  df$correctness_score[1],
  df$contamination_score[1],
  df$structure_score[1]
)
overall <- df$overall_score[1]
grade   <- df$overall_grade[1]
ready   <- df$annotation_ready[1]

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

# ---- Grade color ----
grade_color <- function(g) {
  switch(g,
    "A" = "#4CAF50", "B" = "#8BC34A", "C" = "#FF9800",
    "D" = "#FF5722", "F" = "#F44336", "#999999")
}

# ====================================================================
# 1. QC Radar Chart
# ====================================================================
plot_radar <- function() {
  radar_df <- data.frame(
    dimension = factor(dimensions, levels = dimensions),
    score = scores
  )

  # Close the polygon by repeating first row
  radar_closed <- rbind(radar_df, radar_df[1, ])

  p <- ggplot(radar_closed, aes(x = dimension, y = score, group = 1)) +
    geom_polygon(fill = "#2196F3", alpha = 0.3, color = "#2196F3", linewidth = 1) +
    geom_point(color = "#1565C0", size = 3) +
    geom_text(aes(label = round(score, 1)), vjust = -1.2, size = 3.5, fontface = "bold") +
    scale_y_continuous(limits = c(0, 105), breaks = seq(0, 100, 20)) +
    labs(x = NULL, y = "Score",
         title = paste0("QC Radar — Overall: ", overall, "/100 (Grade ", grade, ")")) +
    theme_classic(base_size = 11) +
    theme(
      panel.grid.major = element_line(color = "grey90"),
      axis.text.x = element_text(size = 10)
    )

  save_plot(p, "qc_radar", w = 7, h = 6)
}

# ====================================================================
# 2. QC Gauge Chart (overall score)
# ====================================================================
plot_gauge <- function() {
  gc <- grade_color(grade)

  gauge_df <- data.frame(
    x = 1, y = 0,
    score = overall,
    label = paste0(overall, "\nGrade ", grade)
  )

  # Background semicircle segments
  n_seg <- 100
  bg_df <- data.frame(
    start = seq(0, pi, length.out = n_seg + 1)[-(n_seg + 1)],
    end   = seq(0, pi, length.out = n_seg + 1)[-1],
    fill  = rep(c("#F44336", "#FF9800", "#FFEB3B", "#8BC34A", "#4CAF50"), each = n_seg / 5)
  )

  p <- ggplot() +
    # Colored background arc
    geom_rect(data = bg_df, inherit.aes = FALSE,
              aes(xmin = start, xmax = end, ymin = -0.05, ymax = 0.05),
              fill = bg_df$fill, color = NA) +
    # Needle (simple approach: just the number)
    annotate("text", x = pi / 2, y = -0.3, label = paste0(round(overall, 1)),
             size = 14, fontface = "bold", color = gc) +
    annotate("text", x = pi / 2, y = -0.55, label = paste0("Grade: ", grade),
             size = 8, color = gc) +
    annotate("text", x = pi / 2, y = -0.75,
             label = ifelse(ready, "PASS - Annotation Ready", "FAIL - Needs Improvement"),
             size = 6, fontface = "bold",
             color = ifelse(ready, "#4CAF50", "#F44336")) +
    # Score labels at extremes
    annotate("text", x = 0, y = -0.2, label = "0", size = 4) +
    annotate("text", x = pi, y = -0.2, label = "100", size = 4) +
    coord_polar(start = -pi / 2) +
    scale_x_continuous(limits = c(0, pi)) +
    scale_y_continuous(limits = c(-1, 0.15)) +
    labs(title = "Assembly Quality Score") +
    theme_void(base_size = 12) +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      panel.border = element_rect(colour = "black", fill = NA, linewidth = 0.5)
    )

  save_plot(p, "qc_gauge", w = 7, h = 6)
}

# ====================================================================
# 3. QC Dimension Scores Bar Chart
# ====================================================================
plot_summary <- function() {
  bar_df <- data.frame(
    dimension = factor(dimensions, levels = rev(dimensions)),
    score = rev(scores),
    weight = rev(c(0.35, 0.15, 0.25, 0.15, 0.10))
  )

  bar_df$color <- ifelse(bar_df$score >= 90, "#4CAF50",
                  ifelse(bar_df$score >= 75, "#8BC34A",
                  ifelse(bar_df$score >= 60, "#FF9800",
                  ifelse(bar_df$score >= 40, "#FF5722", "#F44336"))))

  p <- ggplot(bar_df, aes(x = dimension, y = score, fill = color)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.6) +
    geom_hline(yintercept = 60, linetype = "dashed", color = "red", linewidth = 0.6) +
    geom_hline(yintercept = 75, linetype = "dotted", color = "blue", linewidth = 0.6) +
    geom_text(aes(label = paste0(round(score, 1), " (w=", weight, ")")),
              hjust = -0.15, size = 3.5) +
    scale_fill_identity() +
    scale_y_continuous(limits = c(0, 110)) +
    annotate("text", x = 5.5, y = 62, label = "Annotation-ready (60)", size = 3, color = "red") +
    annotate("text", x = 5.5, y = 77, label = "Good (75)", size = 3, color = "blue") +
    labs(x = NULL, y = "Score (0-100)",
         title = paste0("QC Dimension Scores — Overall: ", overall, "/100 (", grade, ")")) +
    coord_flip() +
    theme_classic(base_size = 11) +
    theme(legend.position = "none")

  save_plot(p, "qc_summary", w = 8, h = 5)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating QC plots with R...\n")
plot_radar()
plot_gauge()
plot_summary()
cat("All QC plots generated.\n")
