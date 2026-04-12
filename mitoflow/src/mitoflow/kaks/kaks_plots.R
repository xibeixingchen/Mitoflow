#!/usr/bin/env Rscript
# MitoFlow Ka/Ks Visualization — ggplot2 + eoffice
#
# Generates 5 publication-quality plots from Ka/Ks results:
#   1. kaks_barplot   — Bar plot of Ka/Ks by gene (category-colored)
#   2. kaks_boxplot   — Box plot of Ka/Ks by functional category
#   3. ka_vs_ks       — Ka vs Ks scatter with diagonal reference lines
#   4. selection_pie  — Pie chart of selection categories
#   5. kaks_dotplot   — Horizontal dot plot of Ka/Ks by gene
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript kaks_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript kaks_plots.R <input.tsv> <output_prefix> [width] [height] [dpi]")
}

tsv_path   <- args[1]
out_prefix <- args[2]
fig_width  <- if (length(args) >= 3) as.numeric(args[3]) else 10
fig_height <- if (length(args) >= 4) as.numeric(args[4]) else 7
fig_dpi    <- if (length(args) >= 5) as.numeric(args[5]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

# Filter valid results (non-NA selection)
df_valid <- df %>% filter(selection != "NA")

# If no valid data, write empty plots and exit
if (nrow(df_valid) == 0) {
  cat("No valid Ka/Ks results to plot\n")
  quit(status = 0)
}

# Ensure numeric types
df_valid$Ka     <- as.numeric(df_valid$Ka)
df_valid$Ks     <- as.numeric(df_valid$Ks)
df_valid$Ka_Ks  <- as.numeric(df_valid$Ka_Ks)

# Category colors (matching Python visualize.py)
cat_colors <- c(
  "Complex I"   = "#FFEC00",
  "Complex III" = "#C8FA28",
  "Complex IV"  = "#FFB4FF",
  "Complex V"   = "#97BE0D",
  "CCM"         = "#328925",
  "Ribosomal"   = "#DBAA73",
  "Other"       = "#AB259D"
)

# Selection colors
sel_colors <- c(
  "purifying" = "#4CAF50",
  "neutral"   = "#2196F3",
  "positive"  = "#F44336",
  "NA"        = "#9E9E9E"
)

# ---- Helper: save plot in 3 formats ----
save_plot <- function(p, name) {
  png_path  <- paste0(out_prefix, "_", name, ".png")
  pdf_path  <- paste0(out_prefix, "_", name, ".pdf")
  pptx_path <- paste0(out_prefix, "_", name, ".pptx")

  ggsave(png_path, p, width = fig_width, height = fig_height, dpi = fig_dpi)
  ggsave(pdf_path, p, width = fig_width, height = fig_height)

  tryCatch({
    topptx(p, pptx_path, width = fig_width, height = fig_height)
  }, error = function(e) {
    warning(paste("topptx failed for", name, ":", e$message))
  })

  cat(paste0("  ", name, ": ", png_path, ", ", pdf_path, ", ", pptx_path, "\n"))
}

# ====================================================================
# 1. Ka/Ks Bar Plot
# ====================================================================
plot_barplot <- function() {
  df_sorted <- df_valid %>%
    arrange(Ka_Ks) %>%
    mutate(gene = factor(gene, levels = gene))

  n_genes <- nrow(df_sorted)
  w <- max(10, n_genes * 0.4)
  h <- 6

  p <- ggplot(df_sorted, aes(x = gene, y = Ka_Ks, fill = category)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.2, width = 0.7) +
    geom_hline(yintercept = 1.0, color = "red", linetype = "dashed", linewidth = 0.6) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = NULL, y = expression(K[a]/K[s]),
         title = expression(K[a]/K[s]~Ratio~by~Gene)) +
    theme_classic(base_size = 10) +
    theme(
      axis.text.x = element_text(angle = 90, hjust = 1, vjust = 0.5, size = 7),
      panel.grid.major.x = element_blank(),
      legend.position = "right"
    )

  ggsave(paste0(out_prefix, "_kaks_barplot.png"), p, width = w, height = h, dpi = fig_dpi)
  ggsave(paste0(out_prefix, "_kaks_barplot.pdf"), p, width = w, height = h)
  tryCatch(topptx(p, paste0(out_prefix, "_kaks_barplot.pptx"), width = w, height = h),
           error = function(e) warning(paste("topptx barplot:", e$message)))
  cat("  kaks_barplot done\n")
}

# ====================================================================
# 2. Ka/Ks Box Plot
# ====================================================================
plot_boxplot <- function() {
  p <- ggplot(df_valid, aes(x = category, y = Ka_Ks, fill = category)) +
    geom_boxplot(alpha = 0.8, outlier.shape = 21) +
    geom_hline(yintercept = 1.0, color = "red", linetype = "dashed", linewidth = 0.6) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = NULL, y = expression(K[a]/K[s]),
         title = expression(K[a]/K[s]~Distribution~by~Functional~Category)) +
    theme_classic(base_size = 11) +
    theme(axis.text.x = element_text(angle = 30, hjust = 1))

  save_plot(p, "kaks_boxplot")
}

# ====================================================================
# 3. Ka vs Ks Scatter
# ====================================================================
plot_scatter <- function() {
  df_scatter <- df_valid %>% filter(Ks > 0)

  if (nrow(df_scatter) == 0) {
    cat("  ka_vs_ks: no valid data (Ks=0 for all)\n")
    return()
  }

  max_val <- max(c(df_scatter$Ks, df_scatter$Ka), na.rm = TRUE) * 1.1

  p <- ggplot(df_scatter, aes(x = Ks, y = Ka, color = category)) +
    geom_point(size = 2.5, alpha = 0.7) +
    geom_abline(intercept = 0, slope = 0.5, linetype = "dotted",  color = "grey40") +
    geom_abline(intercept = 0, slope = 1.0, linetype = "dashed",  color = "red") +
    geom_abline(intercept = 0, slope = 2.0, linetype = "longdash", color = "grey40") +
    scale_color_manual(values = cat_colors, name = "Category") +
    annotate("text", x = max_val * 0.85, y = max_val * 0.5 * 0.85,
             label = "Ka/Ks=0.5", size = 3, color = "grey40") +
    annotate("text", x = max_val * 0.85, y = max_val * 1.0 * 0.85,
             label = "Ka/Ks=1.0", size = 3, color = "red") +
    annotate("text", x = max_val * 0.85, y = max_val * 2.0 * 0.85,
             label = "Ka/Ks=2.0", size = 3, color = "grey40") +
    labs(x = expression(K[s]~(synonymous~substitutions)),
         y = expression(K[a]~(non-synonymous~substitutions)),
         title = expression(K[a]~vs~K[s])) +
    coord_cartesian(xlim = c(0, max_val), ylim = c(0, max_val)) +
    theme_classic(base_size = 11)

  save_plot(p, "ka_vs_ks")
}

# ====================================================================
# 4. Selection Pie Chart
# ====================================================================
plot_pie <- function() {
  df_all <- df  # include NA
  sel_counts <- df_all %>%
    group_by(selection) %>%
    summarise(count = n(), .groups = "drop")

  sel_counts$label <- paste0(tools::toTitleCase(sel_counts$selection),
                              "\n(", sel_counts$count, ")")

  p <- ggplot(sel_counts, aes(x = "", y = count, fill = selection)) +
    geom_bar(stat = "identity", width = 1, color = "white") +
    coord_polar("y", start = 0) +
    scale_fill_manual(values = sel_colors, name = "Selection") +
    geom_text(aes(label = paste0(round(count / sum(count) * 100, 1), "%")),
              position = position_stack(vjust = 0.5), size = 4) +
    labs(title = "Selection Pressure Distribution") +
    theme_void(base_size = 12) +
    theme(
      legend.position = "right",
      panel.border = element_rect(colour = "black", fill = NA, linewidth = 0.5)
    )

  save_plot(p, "selection_pie")
}

# ====================================================================
# 5. Ka/Ks Dot Plot (horizontal)
# ====================================================================
plot_dotplot <- function() {
  df_sorted <- df_valid %>%
    arrange(Ka_Ks) %>%
    mutate(gene = factor(gene, levels = gene))

  n_genes <- nrow(df_sorted)
  h <- max(4, n_genes * 0.25)
  w <- 8

  p <- ggplot(df_sorted, aes(x = Ka_Ks, y = gene, color = category)) +
    geom_point(size = 2.5, alpha = 0.8) +
    geom_vline(xintercept = 1.0, color = "red", linetype = "dashed", linewidth = 0.6) +
    scale_color_manual(values = cat_colors, name = "Category") +
    labs(x = expression(K[a]/K[s]), y = NULL,
         title = expression(K[a]/K[s]~Ratio~by~Gene)) +
    theme_classic(base_size = 10) +
    theme(
      axis.text.y = element_text(size = 7),
      panel.grid.major.y = element_blank(),
      legend.position = "right"
    )

  ggsave(paste0(out_prefix, "_kaks_dotplot.png"), p, width = w, height = h, dpi = fig_dpi)
  ggsave(paste0(out_prefix, "_kaks_dotplot.pdf"), p, width = w, height = h)
  tryCatch(topptx(p, paste0(out_prefix, "_kaks_dotplot.pptx"), width = w, height = h),
           error = function(e) warning(paste("topptx dotplot:", e$message)))
  cat("  kaks_dotplot done\n")
}

# ====================================================================
# Main
# ====================================================================
cat("Generating Ka/Ks plots with R...\n")
plot_barplot()
plot_boxplot()
plot_scatter()
plot_pie()
plot_dotplot()
cat("All Ka/Ks plots generated.\n")
