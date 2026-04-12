#!/usr/bin/env Rscript
# MitoFlow NUMT Visualization — RIdeogram + ggplot2 + eoffice
#
# Generates publication-quality plots from NUMT detection results:
#   1. numt_ideogram   — Nuclear chromosome ideogram with NUMT markers (RIdeogram)
#   2. numt_barplot    — Bar plot of NUMT count by category
#   3. numt_identity   — Histogram of NUMT identity distribution
#   4. numt_mito_map   — Dot plot of NUMT positions on mitochondrial genome
#   5. numt_chr_dist   — NUMT count per nuclear chromosome
#
# Output: PNG, PDF, PPTX (via eoffice::topptx) for each plot
#
# Usage:
#   Rscript numt_plots.R <input.tsv> <output_prefix> <karyotype.tsv> [width] [height] [dpi]

suppressPackageStartupMessages({
  library(RIdeogram)
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# ---- Parse arguments ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Usage: Rscript numt_plots.R <input.tsv> <output_prefix> <karyotype.tsv> [width] [height] [dpi]")
}

tsv_path   <- args[1]
out_prefix <- args[2]
karyo_path <- args[3]
fig_width  <- if (length(args) >= 4) as.numeric(args[4]) else 10
fig_height <- if (length(args) >= 5) as.numeric(args[5]) else 7
fig_dpi    <- if (length(args) >= 6) as.numeric(args[6]) else 300

# ---- Read data ----
df <- read.delim(tsv_path, header = TRUE, stringsAsFactors = FALSE)

if (nrow(df) == 0) {
  cat("No NUMT results to plot\n")
  quit(status = 0)
}

# Ensure numeric types
df$Identity <- as.numeric(df$Identity)
df$Length   <- as.numeric(df$Length)
df$Start    <- as.numeric(df$Start)
df$End      <- as.numeric(df$End)
df$MitoStart <- as.numeric(df$MitoStart)
df$MitoEnd   <- as.numeric(df$MitoEnd)

# Category colors
cat_colors <- c(
  "intact"   = "#4CAF50",
  "partial"  = "#FF9800",
  "chimeric" = "#F44336"
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
# 1. NUMT Ideogram (RIdeogram)
# ====================================================================
plot_ideogram <- function() {
  karyo <- read.delim(karyo_path, header = TRUE, stringsAsFactors = FALSE)

  # Build marker data for RIdeogram label
  # RIdeogram marker format: Type, Shape, Chr, Start, End, color
  markers <- data.frame(
    Type  = df$Category,
    Shape = "box",
    Chr   = df$Chr,
    Start = df$Start,
    End   = df$End,
    color = ifelse(df$Category == "intact", "4CAF50",
            ifelse(df$Category == "partial", "FF9800", "F44336")),
    stringsAsFactors = FALSE
  )

  svg_file <- paste0(out_prefix, "_numt_ideogram.svg")

  tryCatch({
    ideogram(
      karyotype = karyo,
      label     = markers,
      label_type = "marker",
      output    = svg_file,
      width     = fig_width * 5
    )

    # Convert SVG to PNG/PDF via rsvg (better gradient support than convertSVG)
    png_path <- paste0(out_prefix, "_numt_ideogram.png")
    pdf_path <- paste0(out_prefix, "_numt_ideogram.pdf")

    tryCatch({
      library(rsvg)
      rsvg_png(svg_file, png_path, width = fig_width * fig_dpi * 5, height = fig_height * fig_dpi * 5)
      rsvg_pdf(svg_file, pdf_path)
    }, error = function(e) {
      # Fallback to RIdeogram's built-in converter
      tryCatch({
        convertSVG(svg_file, device = "png", dpi = fig_dpi)
        convertSVG(svg_file, device = "pdf")
      }, error = function(e2) {
        warning(paste("SVG conversion failed:", e2$message))
      })
    })

    cat("  numt_ideogram done\n")
  }, error = function(e) {
    cat(paste0("  numt_ideogram skipped: ", e$message, "\n"))
  })
}

# ====================================================================
# 2. NUMT Category Bar Plot
# ====================================================================
plot_barplot <- function() {
  cat_counts <- df %>%
    group_by(Category) %>%
    summarise(Count = n(), .groups = "drop")

  cat_counts$Category <- factor(cat_counts$Category,
                                 levels = c("intact", "partial", "chimeric"))

  p <- ggplot(cat_counts, aes(x = Category, y = Count, fill = Category)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.3, width = 0.6) +
    geom_text(aes(label = Count), vjust = -0.5, size = 4) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = NULL, y = "NUMT Count",
         title = "NUMT Distribution by Category") +
    theme_classic(base_size = 12)

  save_plot(p, "numt_barplot", w = 6, h = 5)
}

# ====================================================================
# 3. NUMT Identity Distribution
# ====================================================================
plot_identity <- function() {
  p <- ggplot(df, aes(x = Identity, fill = Category)) +
    geom_histogram(bins = 30, color = "black", linewidth = 0.2, alpha = 0.8) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = "Identity (%)", y = "Count",
         title = "NUMT Identity Distribution") +
    theme_classic(base_size = 12)

  save_plot(p, "numt_identity", w = 7, h = 5)
}

# ====================================================================
# 4. NUMT Mito Coverage Map (dot plot on mitochondrial coordinates)
# ====================================================================
plot_mito_map <- function() {
  p <- ggplot(df, aes(x = (MitoStart + MitoEnd) / 2, y = Identity,
                       color = Category, size = Length)) +
    geom_point(alpha = 0.7) +
    scale_color_manual(values = cat_colors, name = "Category") +
    scale_size_continuous(name = "Length (bp)", range = c(1, 6)) +
    labs(x = "Mitochondrial Position (bp)", y = "Identity (%)",
         title = "NUMT Coverage on Mitochondrial Genome") +
    theme_classic(base_size = 11) +
    theme(legend.position = "right")

  save_plot(p, "numt_mito_map", w = 9, h = 5)
}

# ====================================================================
# 5. NUMT per Chromosome Distribution
# ====================================================================
plot_chr_dist <- function() {
  chr_counts <- df %>%
    group_by(Chr, Category) %>%
    summarise(Count = n(), .groups = "drop")

  chr_order <- df %>%
    group_by(Chr) %>%
    summarise(Total = n(), .groups = "drop") %>%
    arrange(desc(Total))

  chr_counts$Chr <- factor(chr_counts$Chr, levels = chr_order$Chr)

  n_chr <- length(chr_order$Chr)
  w <- max(8, n_chr * 0.5)

  p <- ggplot(chr_counts, aes(x = Chr, y = Count, fill = Category)) +
    geom_bar(stat = "identity", color = "black", linewidth = 0.2, width = 0.7) +
    scale_fill_manual(values = cat_colors, name = "Category") +
    labs(x = "Nuclear Chromosome", y = "NUMT Count",
         title = "NUMT Distribution by Nuclear Chromosome") +
    theme_classic(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1))

  save_plot(p, "numt_chr_dist", w = w, h = 5)
}

# ====================================================================
# Main
# ====================================================================
cat("Generating NUMT plots with R...\n")
plot_ideogram()
plot_barplot()
plot_identity()
plot_mito_map()
plot_chr_dist()
cat("All NUMT plots generated.\n")
