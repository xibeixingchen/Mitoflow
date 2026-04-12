#!/usr/bin/env Rscript
# MitoFlow Repeat Visualization — ggplot2 + eoffice
#
# Generates publication-quality plots from repeat detection results:
#   1. repeat_ssr_dist      — SSR count by category (mono/di/tri/tetra/penta/hexa)
#   2. repeat_ssr_motif      — Top 20 most frequent SSR motifs
#   3. repeat_tandem_period  — Tandem repeat period size distribution
#   4. repeat_long_map       — Linear genome map with long repeat arcs
#   5. repeat_long_type      — Pie chart of long repeat type distribution
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript repeat_plots.R <ssr.tsv> <tandem.tsv> <long.tsv> <output_prefix> [genome_length] [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("Usage: Rscript repeat_plots.R <ssr.tsv> <tandem.tsv> <long.tsv> <output_prefix> [genome_length] [width] [height] [dpi]")
}

ssr_path    <- args[1]
tandem_path <- args[2]
long_path   <- args[3]
out_prefix  <- args[4]
genome_len  <- if (length(args) >= 5) as.numeric(args[5]) else 0
fig_width   <- if (length(args) >= 6) as.numeric(args[6]) else 10
fig_height  <- if (length(args) >= 7) as.numeric(args[7]) else 7
fig_dpi     <- if (length(args) >= 8) as.numeric(args[8]) else 300

# ---- Color palettes ----
ssr_cat_colors <- c(
  "mono"  = "#e74c3c",
  "di"    = "#3498db",
  "tri"   = "#2ecc71",
  "tetra" = "#f39c12",
  "penta" = "#9b59b6",
  "hexa"  = "#1abc9c"
)

long_type_colors <- c(
  "forward"    = "#e74c3c",
  "reverse"    = "#3498db",
  "complement" = "#2ecc71",
  "palindromic" = "#f39c12"
)

long_orient_colors <- c(
  "direct"   = "#e74c3c",
  "inverted" = "#3498db"
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
# 1. SSR Distribution by Category
# ====================================================================
plot_ssr_dist <- function() {
  if (!file.exists(ssr_path)) {
    cat("  repeat_ssr_dist skipped: SSR file not found\n")
    return()
  }
  ssr <- read.delim(ssr_path, header = TRUE, stringsAsFactors = FALSE)
  if (nrow(ssr) == 0) {
    cat("  repeat_ssr_dist skipped: no SSR data\n")
    return()
  }

  ssr$category <- factor(ssr$category,
                          levels = c("mono", "di", "tri", "tetra", "penta", "hexa"))

  cat_counts <- ssr %>%
    group_by(category) %>%
    summarise(Count = n(), .groups = "drop") %>%
    filter(!is.na(category))

  p <- ggplot(cat_counts, aes(x = category, y = Count, fill = category)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.6) +
    geom_text(aes(label = Count), vjust = -0.5, size = 4) +
    scale_fill_manual(values = ssr_cat_colors, name = "Category") +
    labs(x = NULL, y = "SSR Count",
         title = "SSR Distribution by Category") +
    theme_classic(base_size = 12)

  save_plot(p, "repeat_ssr_dist", w = 7, h = 5)
}

# ====================================================================
# 2. Top SSR Motifs
# ====================================================================
plot_ssr_motif <- function() {
  if (!file.exists(ssr_path)) {
    cat("  repeat_ssr_motif skipped: SSR file not found\n")
    return()
  }
  ssr <- read.delim(ssr_path, header = TRUE, stringsAsFactors = FALSE)
  if (nrow(ssr) == 0) {
    cat("  repeat_ssr_motif skipped: no SSR data\n")
    return()
  }

  motif_counts <- ssr %>%
    group_by(motif) %>%
    summarise(Count = n(), .groups = "drop") %>%
    arrange(desc(Count)) %>%
    head(20)

  motif_counts$motif <- factor(motif_counts$motif,
                                levels = rev(motif_counts$motif))

  n_motifs <- nrow(motif_counts)
  h <- max(4, n_motifs * 0.35)

  p <- ggplot(motif_counts, aes(x = motif, y = Count)) +
    geom_bar(stat = "identity", fill = "#3498db", color = "black", linewidth = 0.3) +
    geom_text(aes(label = Count), hjust = -0.3, size = 3.5) +
    coord_flip() +
    labs(x = NULL, y = "Count",
         title = "Top SSR Motifs") +
    theme_classic(base_size = 11) +
    theme(axis.text.y = element_text(family = "mono", size = 9))

  save_plot(p, "repeat_ssr_motif", w = 8, h = h)
}

# ====================================================================
# 3. Tandem Repeat Period Distribution
# ====================================================================
plot_tandem_period <- function() {
  if (!file.exists(tandem_path)) {
    cat("  repeat_tandem_period skipped: tandem file not found\n")
    return()
  }
  tandem <- read.delim(tandem_path, header = TRUE, stringsAsFactors = FALSE)
  if (nrow(tandem) == 0) {
    cat("  repeat_tandem_period skipped: no tandem data\n")
    return()
  }

  tandem$period_size <- as.numeric(tandem$period_size)

  # Bin period sizes
  tandem$period_bin <- cut(tandem$period_size,
                            breaks = c(0, 6, 15, 30, 100, Inf),
                            labels = c("2-6 bp", "7-15 bp", "16-30 bp", "31-100 bp", ">100 bp"),
                            right = TRUE)

  bin_counts <- tandem %>%
    group_by(period_bin) %>%
    summarise(Count = n(), .groups = "drop") %>%
    filter(!is.na(period_bin))

  period_colors <- c(
    "2-6 bp"    = "#2ecc71",
    "7-15 bp"   = "#3498db",
    "16-30 bp"  = "#f39c12",
    "31-100 bp" = "#e74c3c",
    ">100 bp"   = "#9b59b6"
  )

  p <- ggplot(bin_counts, aes(x = period_bin, y = Count, fill = period_bin)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.6) +
    geom_text(aes(label = Count), vjust = -0.5, size = 4) +
    scale_fill_manual(values = period_colors, name = "Period Size") +
    labs(x = "Period Size", y = "Count",
         title = "Tandem Repeat Period Size Distribution") +
    theme_classic(base_size = 12)

  save_plot(p, "repeat_tandem_period", w = 7, h = 5)
}

# ====================================================================
# 4. Long Repeat Genome Map
# ====================================================================
plot_long_map <- function() {
  if (!file.exists(long_path)) {
    cat("  repeat_long_map skipped: long repeat file not found\n")
    return()
  }
  long_df <- read.delim(long_path, header = TRUE, stringsAsFactors = FALSE)
  if (nrow(long_df) == 0) {
    cat("  repeat_long_map skipped: no long repeat data\n")
    return()
  }

  if (genome_len <= 0) {
    # Estimate from data
    genome_len <<- max(c(long_df$copy1_end, long_df$copy2_end), na.rm = TRUE) * 1.1
  }

  long_df$copy1_start <- as.numeric(long_df$copy1_start)
  long_df$copy1_end   <- as.numeric(long_df$copy1_end)
  long_df$copy2_start <- as.numeric(long_df$copy2_start)
  long_df$copy2_end   <- as.numeric(long_df$copy2_end)
  long_df$length      <- as.numeric(long_df$length)

  # Build segment data for genome backbone
  backbone <- data.frame(x = 0, xend = genome_len, y = 0, yend = 0)

  # Build arc data: for each repeat pair, create an arc curve
  arc_data <- do.call(rbind, lapply(1:nrow(long_df), function(i) {
    rp <- long_df[i, ]
    mid1 <- (rp$copy1_start + rp$copy1_end) / 2
    mid2 <- (rp$copy2_start + rp$copy2_end) / 2
    arc_h <- 0.3 + i * 0.3
    theta <- seq(0, pi, length.out = 50)
    data.frame(
      x = mid1 + (mid2 - mid1) * (1 - cos(theta)) / 2,
      y = arc_h * sin(theta),
      group = i,
      orientation = rp$orientation,
      label = paste0(rp$repeat_id, " (", format(rp$length, big.mark = ","), " bp)")
    )
  }))

  # Build rect data for copy positions
  rect_data <- do.call(rbind, lapply(1:nrow(long_df), function(i) {
    rp <- long_df[i, ]
    rbind(
      data.frame(xmin = rp$copy1_start, xmax = rp$copy1_end,
                 group = i, orientation = rp$orientation, copy = 1),
      data.frame(xmin = rp$copy2_start, xmax = rp$copy2_end,
                 group = i, orientation = rp$orientation, copy = 2)
    )
  }))

  # Label positions (top of each arc)
  label_data <- do.call(rbind, lapply(1:nrow(long_df), function(i) {
    rp <- long_df[i, ]
    mid1 <- (rp$copy1_start + rp$copy1_end) / 2
    mid2 <- (rp$copy2_start + rp$copy2_end) / 2
    arc_h <- 0.3 + i * 0.3
    data.frame(
      x = (mid1 + mid2) / 2,
      y = arc_h + 0.08,
      label = paste0(rp$repeat_id, " (", format(rp$length, big.mark = ","), " bp)"),
      orientation = rp$orientation
    )
  }))

  n_rp <- nrow(long_df)
  w <- max(10, genome_len / 50000)
  h <- max(4, 2 + n_rp * 0.5)

  p <- ggplot() +
    # Genome backbone
    geom_segment(data = backbone, aes(x = x, xend = xend, y = y, yend = y),
                 color = "#2c3e50", linewidth = 2) +
    # Repeat copy rectangles
    geom_rect(data = rect_data,
              aes(xmin = xmin, xmax = xmax, ymin = -0.1, ymax = 0.1,
                  fill = orientation),
              alpha = 0.8, color = "black", linewidth = 0.3) +
    # Arcs
    geom_path(data = arc_data, aes(x = x, y = y, group = group,
                                    color = orientation),
              linewidth = 0.8, alpha = 0.7) +
    # Labels
    geom_text(data = label_data, aes(x = x, y = y, label = label, color = orientation),
              size = 2.5, vjust = 0, fontface = "bold", show.legend = FALSE) +
    scale_color_manual(values = long_orient_colors, name = "Orientation") +
    scale_fill_manual(values = long_orient_colors, name = "Orientation") +
    labs(x = "Position (bp)", y = NULL,
         title = paste0("Long Repeat Map (", n_rp, " pairs)")) +
    theme_classic(base_size = 11) +
    theme(axis.line.y = element_blank(),
          axis.text.y = element_blank(),
          axis.ticks.y = element_blank())

  save_plot(p, "repeat_long_map", w = w, h = h)
}

# ====================================================================
# 5. Long Repeat Type Pie Chart
# ====================================================================
plot_long_type <- function() {
  if (!file.exists(long_path)) {
    cat("  repeat_long_type skipped: long repeat file not found\n")
    return()
  }
  long_df <- read.delim(long_path, header = TRUE, stringsAsFactors = FALSE)
  if (nrow(long_df) == 0) {
    cat("  repeat_long_type skipped: no long repeat data\n")
    return()
  }

  type_counts <- long_df %>%
    group_by(type) %>%
    summarise(Count = n(), .groups = "drop")

  # Compute percentages for labels
  type_counts$prop <- type_counts$Count / sum(type_counts$Count)
  type_counts$label <- paste0(type_counts$type, "\n",
                               round(type_counts$prop * 100, 1), "%")

  p <- ggplot(type_counts, aes(x = "", y = Count, fill = type)) +
    geom_bar(stat = "identity", color = "white", linewidth = 0.5, width = 1) +
    geom_text(aes(label = label),
              position = position_stack(vjust = 0.5), size = 3.5) +
    coord_polar("y", start = 0) +
    scale_fill_manual(values = long_type_colors, name = "Repeat Type") +
    labs(title = "Long Repeat Type Distribution") +
    theme_void(base_size = 12) +
    theme(plot.title = element_text(hjust = 0.5, face = "bold"))

  save_plot(p, "repeat_long_type", w = 6, h = 6)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating Repeat plots with R...\n")
plot_ssr_dist()
plot_ssr_motif()
plot_tandem_period()
plot_long_map()
plot_long_type()
cat("All Repeat plots generated.\n")
