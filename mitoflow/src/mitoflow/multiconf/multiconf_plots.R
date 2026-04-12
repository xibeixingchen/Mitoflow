#!/usr/bin/env Rscript
# MitoFlow Multiconf Visualization — ggplot2 + eoffice
#
# Generates 4 publication-quality plots from multi-configuration analysis:
#   1. multiconf_repeat_map    — Linear genome map with repeat arcs
#   2. multiconf_config_diagram — Circular representations of master/subcircles
#   3. multiconf_recomb_summary — Bar chart of repeat lengths by repeat_type
#   4. multiconf_type_dist     — Pie chart of repeat type distribution
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript multiconf_plots.R <repeats.tsv> <output_prefix> <configs.tsv> [genome_length] [width] [height] [dpi]

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Usage: Rscript multiconf_plots.R <repeats.tsv> <output_prefix> <configs.tsv> [genome_length] [width] [height] [dpi]")
}

reps_path  <- args[1]
out_prefix <- args[2]
conf_path  <- args[3]
genome_len <- if (length(args) >= 4) as.numeric(args[4]) else 0
fig_width  <- if (length(args) >= 5) as.numeric(args[5]) else 10
fig_height <- if (length(args) >= 6) as.numeric(args[6]) else 7
fig_dpi    <- if (length(args) >= 7) as.numeric(args[7]) else 300

# ---- Read data ----
df_reps <- read.delim(reps_path, header = TRUE, stringsAsFactors = FALSE)
df_conf <- read.delim(conf_path, header = TRUE, stringsAsFactors = FALSE)

if (nrow(df_reps) == 0) {
  cat("No repeat pairs to plot\n")
  quit(status = 0)
}

# Ensure numeric types
df_reps$copy1_start <- as.numeric(df_reps$copy1_start)
df_reps$copy1_end   <- as.numeric(df_reps$copy1_end)
df_reps$copy2_start <- as.numeric(df_reps$copy2_start)
df_reps$copy2_end   <- as.numeric(df_reps$copy2_end)
df_reps$length      <- as.numeric(df_reps$length)
df_reps$identity    <- as.numeric(df_reps$identity)
if ("recombination_ratio" %in% names(df_reps)) {
  df_reps$recombination_ratio <- as.numeric(df_reps$recombination_ratio)
}

df_conf$size       <- as.numeric(df_conf$size)
df_conf$gene_count <- as.integer(df_conf$gene_count)
df_conf$is_major   <- as.logical(df_conf$is_major)

# Orientation colors
orient_colors <- c("direct" = "#e74c3c", "inverted" = "#3498db")
# Type colors for pie chart
type_colors <- c("direct" = "#e74c3c", "inverted" = "#3498db")
# Config colors
config_colors <- c("#2ecc71", "#e67e22", "#9b59b6", "#1abc9c",
                   "#e74c3c", "#3498db", "#f1c40f", "#95a5a6")

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
# 1. Repeat Map — Linear genome with arcs connecting repeat copies
# ====================================================================
plot_repeat_map <- function() {
  if (genome_len <= 0) {
    genome_len <<- max(c(df_reps$copy1_end, df_reps$copy2_end)) * 1.05
  }

  # Build arc data: for each repeat, generate bezier curve points
  arc_list <- lapply(seq_len(nrow(df_reps)), function(i) {
    mid1 <- (df_reps$copy1_start[i] + df_reps$copy1_end[i]) / 2
    mid2 <- (df_reps$copy2_start[i] + df_reps$copy2_end[i]) / 2
    y_off <- 0.5 + (i - 1) * 0.6
    theta <- seq(0, pi, length.out = 50)
    data.frame(
      x = mid1 + (mid2 - mid1) * (1 - cos(theta)) / 2,
      y = (y_off + 0.3) * sin(theta),
      group = df_reps$repeat_id[i],
      repeat_type = df_reps$repeat_type[i]
    )
  })
  arcs <- do.call(rbind, arc_list)

  # Build copy rectangles
  copies <- rbind(
    data.frame(
      xmin = df_reps$copy1_start, xmax = df_reps$copy1_end,
      ymin = -0.15, ymax = 0.15,
      repeat_id = df_reps$repeat_id,
      repeat_type = df_reps$repeat_type
    ),
    data.frame(
      xmin = df_reps$copy2_start, xmax = df_reps$copy2_end,
      ymin = -0.15, ymax = 0.15,
      repeat_id = df_reps$repeat_id,
      repeat_type = df_reps$repeat_type
    )
  )

  # Labels at arc peaks
  labels <- data.frame(
    x = (df_reps$copy1_start + df_reps$copy1_end + df_reps$copy2_start + df_reps$copy2_end) / 4,
    y = 0.5 + (seq_len(nrow(df_reps)) - 1) * 0.6 + 0.3 + 0.15,
    label = paste0(df_reps$repeat_id, " (", df_reps$repeat_type, ", ",
                   format(df_reps$length, big.mark = ","), " bp)"),
    repeat_type = df_reps$repeat_type
  )

  n_reps <- nrow(df_reps)
  w <- max(10, genome_len / 50000)
  h <- max(4, 2 + n_reps * 0.6)

  p <- ggplot() +
    # Genome backbone
    geom_segment(aes(x = 0, xend = genome_len, y = 0, yend = 0),
                 color = "#2c3e50", linewidth = 2) +
    # Repeat copy rectangles
    geom_rect(data = copies, aes(xmin = xmin, xmax = xmax,
                                  ymin = ymin, ymax = ymax,
                                  fill = repeat_type),
              color = "black", linewidth = 0.3, alpha = 0.8) +
    # Connecting arcs
    geom_line(data = arcs, aes(x = x, y = y, group = group,
                                color = repeat_type),
              linewidth = 1, alpha = 0.7) +
    # Labels
    geom_text(data = labels, aes(x = x, y = y, label = label),
              size = 2.5, fontface = "bold",
              color = ifelse(labels$repeat_type == "direct", "#e74c3c", "#3498db")) +
    scale_fill_manual(values = orient_colors, name = "Orientation") +
    scale_color_manual(values = orient_colors, name = "Orientation") +
    labs(x = "Genome Position (bp)", y = NULL,
         title = paste0("Repeat Map (", n_reps, " pairs, ",
                        format(genome_len, big.mark = ","), " bp)")) +
    theme_classic(base_size = 10) +
    theme(axis.line.y = element_blank(),
          axis.text.y = element_blank(),
          axis.ticks.y = element_blank())

  save_plot(p, "multiconf_repeat_map", w = w, h = h)
}

# ====================================================================
# 2. Configuration Diagram — Circular representations
# ====================================================================
plot_config_diagram <- function() {
  if (genome_len <= 0) {
    genome_len <<- max(c(df_reps$copy1_end, df_reps$copy2_end)) * 1.05
  }

  # Master circle + subgenomic circles
  all_configs <- rbind(
    data.frame(config_name = "Master Circle", size = genome_len,
               gene_count = NA_integer_, is_major = TRUE, idx = 0),
    data.frame(config_name = df_conf$config_name,
               size = df_conf$size,
               gene_count = df_conf$gene_count,
               is_major = df_conf$is_major,
               idx = seq_len(nrow(df_conf)))
  )

  n_panels <- nrow(all_configs)
  n_cols <- min(n_panels, 4)
  n_rows <- ceiling(n_panels / n_cols)

  # Build polygon data for filled circles, one per panel
  circle_data <- do.call(rbind, lapply(seq_len(nrow(all_configs)), function(i) {
    row <- all_configs[i, ]
    theta <- seq(0, 2 * pi, length.out = 100)
    data.frame(
      x = cos(theta),
      y = sin(theta),
      panel = paste0(i, ": ", row$config_name),
      config_idx = i
    )
  }))

  # Build label data
  label_data <- do.call(rbind, lapply(seq_len(nrow(all_configs)), function(i) {
    row <- all_configs[i, ]
    label_text <- paste0(row$config_name, "\n",
                         format(row$size, big.mark = ","), " bp")
    if (!is.na(row$gene_count) && row$gene_count > 0) {
      label_text <- paste0(label_text, "\n", row$gene_count, " genes")
    }
    data.frame(
      x = 0, y = 0,
      label = label_text,
      panel = paste0(i, ": ", row$config_name),
      config_idx = i,
      bold = row$is_major
    )
  }))

  # Assign colors per config
  circle_data$color <- sapply(circle_data$config_idx, function(i) {
    row <- all_configs[i, ]
    if (row$idx == 0) return("#2c3e50")
    config_colors[((row$idx - 1) %% length(config_colors)) + 1]
  })

  circle_data$panel <- factor(circle_data$panel,
                               levels = unique(circle_data$panel))
  label_data$panel <- factor(label_data$panel,
                              levels = unique(label_data$panel))

  w <- n_cols * 4
  h <- n_rows * 4.5

  p <- ggplot() +
    geom_polygon(data = circle_data, aes(x = x, y = y, group = panel),
                 fill = circle_data$color, alpha = 0.1,
                 color = circle_data$color, linewidth = 1.5) +
    geom_text(data = label_data, aes(x = x, y = y, label = label),
              size = 3, fontface = ifelse(label_data$bold, "bold", "plain")) +
    facet_wrap(~ panel, ncol = n_cols) +
    coord_fixed() +
    labs(title = paste0("Multi-configuration Diagram (",
                        n_panels, " configurations)")) +
    theme_void(base_size = 10) +
    theme(strip.text = element_text(size = 8, face = "bold"),
          plot.title = element_text(hjust = 0.5, face = "bold", size = 12))

  save_plot(p, "multiconf_config_diagram", w = w, h = h)
}

# ====================================================================
# 3. Recombination Summary — Bar chart of repeat lengths by repeat_type
# ====================================================================
plot_recomb_summary <- function() {
  df_reps$repeat_type <- factor(df_reps$repeat_type,
                                 levels = c("direct", "inverted"))

  n_reps <- nrow(df_reps)
  w <- max(8, n_reps * 1.2)

  p <- ggplot(df_reps, aes(x = repeat_id, y = length, fill = repeat_type)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.7) +
    geom_text(aes(label = paste0(format(length, big.mark = ","), " bp\n", repeat_type)),
              vjust = -0.3, size = 2.5) +
    scale_fill_manual(values = orient_colors, name = "Orientation") +
    labs(x = NULL, y = "Repeat Length (bp)",
         title = "Repeat Pair Summary") +
    theme_classic(base_size = 10) +
    theme(axis.text.x = element_text(angle = 30, hjust = 1, vjust = 1))

  # Add recombination ratio annotation if available
  if ("recombination_ratio" %in% names(df_reps) &&
      any(!is.na(df_reps$recombination_ratio))) {
    recomb_labels <- data.frame(
      x = df_reps$repeat_id,
      y = df_reps$length / 2,
      label = ifelse(!is.na(df_reps$recombination_ratio),
                     paste0("Rec: ", sprintf("%.1f%%", df_reps$recombination_ratio * 100)),
                     "")
    )
    recomb_labels <- recomb_labels[recomb_labels$label != "", , drop = FALSE]
    if (nrow(recomb_labels) > 0) {
      p <- p + geom_text(data = recomb_labels, aes(x = x, y = y, label = label),
                         color = "white", fontface = "bold", size = 2.5,
                         inherit.aes = FALSE)
    }
  }

  save_plot(p, "multiconf_recomb_summary", w = w, h = 5)
}

# ====================================================================
# 4. Repeat Type Distribution — Pie chart
# ====================================================================
plot_type_dist <- function() {
  type_counts <- df_reps %>%
    group_by(repeat_type) %>%
    summarise(Count = n(), .groups = "drop")

  type_counts$repeat_type <- factor(type_counts$repeat_type,
                                     levels = c("direct", "inverted"))

  p <- ggplot(type_counts, aes(x = "", y = Count, fill = repeat_type)) +
    geom_bar(stat = "identity", width = 1, color = "white", linewidth = 0.5) +
    coord_polar("y", start = 0) +
    geom_text(aes(label = paste0(Count, " (", sprintf("%.1f%%", Count / sum(Count) * 100), ")")),
              position = position_stack(vjust = 0.5), size = 4) +
    scale_fill_manual(values = orient_colors, name = "Orientation") +
    labs(title = "Repeat Type Distribution") +
    theme_void(base_size = 12) +
    theme(plot.title = element_text(hjust = 0.5, face = "bold"))

  save_plot(p, "multiconf_type_dist", w = 6, h = 6)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating Multiconf plots with R...\n")
plot_repeat_map()
plot_config_diagram()
plot_recomb_summary()
plot_type_dist()
cat("All Multiconf plots generated.\n")
