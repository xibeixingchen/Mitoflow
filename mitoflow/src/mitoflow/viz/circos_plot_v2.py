#!/usr/bin/env python3
"""OGDraw-style circular mitochondrial genome map using pycirclize."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from pycirclize import Circos

from .config import ColorConfig, CATEGORY_LABELS

# Single source of truth for colors
_color_config = ColorConfig()

# Intron color from centralized config (white)
_INTRON_HEX = _color_config.get_hex("intron")


def _gene_color_hex(gene_name: str, gene_type: str = "CDS") -> str:
    """Get hex color for a gene, falling back to other_cds."""
    return _color_config.gene_color_hex(gene_name, gene_type)


def _build_legend_items() -> list[tuple[str, str]]:
    """Build legend items from the centralized category labels and colors."""
    items = []
    for category, label in CATEGORY_LABELS.items():
        if category in ("repeat", "mtpt"):
            continue  # skip non-gene categories in circular map legend
        items.append((label, _color_config.get_hex(category)))
    return items


LEGEND_ITEMS = _build_legend_items()


def classify_gene(name: str, gene_type: str = "CDS") -> str:
    """Classify gene into functional category using centralized config."""
    return _color_config.classify_gene(name, gene_type)


def parse_genbank(gb_file, gc_window=200):
    """Parse GenBank file and extract gene positions and GC content."""
    raw = Path(gb_file).read_text(encoding="utf-8", errors="replace")
    lines_all = raw.splitlines()
    blocks = re.split(r"\n     gene ", raw)
    genes, seen = [], set()
    for block in blocks[1:]:
        bl = block.split("\n")
        loc = bl[0].strip()
        strand = 1
        if "complement" in loc:
            strand = -1
            loc = re.sub(r"complement\(|\)$", "", loc)
        has_intron = "join" in loc
        exons = []
        if has_intron:
            for p in re.sub(r"join\(|\)$", "", loc).split(","):
                nums = [int(x) for x in re.findall(r"\d+", p)]
                if len(nums) >= 2:
                    exons.append((nums[0], nums[1]))
            if not exons:
                continue
            start, end = exons[0][0], exons[-1][1]
        else:
            nums = [int(x) for x in re.findall(r"\d+", loc)]
            if len(nums) < 2:
                continue
            start, end = nums[0], nums[1]
            exons.append((start, end))
        name = None
        for line in bl[1:8]:
            m = re.search(r'/gene="([^"]+)"', line)
            if m:
                name = m.group(1)
                break
        if not name or name in seen:
            continue
        seen.add(name)
        category = classify_gene(name)
        color = _gene_color_hex(name)
        genes.append({
            "name": name, "start": start, "end": end, "strand": strand,
            "has_intron": has_intron, "exons": exons, "category": category,
            "color": color, "mid": (start + end) / 2, "len": abs(end - start),
        })

    # Extract sequence
    in_seq = False
    seq_parts = []
    for line in lines_all:
        line = line.strip()
        if line.startswith("ORIGIN"):
            in_seq = True
            continue
        if line.startswith("//"):
            break
        if in_seq:
            seq_parts.append(re.sub(r"[^a-zA-Z]", "", line))
    seq = "".join(seq_parts).upper()
    gl = len(seq)

    # GC content
    gc_data = []
    for i in range(gl // gc_window):
        s, e = i * gc_window, min((i + 1) * gc_window, gl)
        w = seq[s:e]
        wl = len(w)
        gc_data.append({
            "start": s, "end": e, "mid": (s + e) / 2,
            "gc": (w.count("G") + w.count("C")) / wl if wl else 0,
        })
    return {"genes": genes, "gc": gc_data, "genome_length": gl}


def spread_labels(mids, gl, min_gap=4000, moved_threshold=4000):
    """Spread labels around the circular genome to avoid overlaps."""
    n = len(mids)
    if n <= 1:
        return list(mids), [False] * n
    idx = sorted(range(n), key=lambda i: mids[i])
    adj = [mids[i] for i in idx]
    orig = list(adj)
    for _ in range(40):
        mv = False
        for i in range(1, n):
            g = adj[i] - adj[i - 1]
            if g < min_gap:
                s = (min_gap - g) / 2
                adj[i - 1] -= s
                adj[i] += s
                mv = True
        gw = (adj[0] + gl) - adj[-1]
        if gw < min_gap:
            s = (min_gap - gw) / 2
            adj[-1] -= s
            adj[0] += s
        if not mv:
            break
    adj = [a % gl for a in adj]
    wm = [abs(a - o) > moved_threshold for a, o in zip(adj, orig)]
    rp, rm = [0.0] * n, [False] * n
    for k, i in enumerate(idx):
        rp[i] = adj[k]
        rm[i] = wm[k]
    return rp, rm


def _label_ha(x, gl, strand):
    """Determine horizontal alignment for a label at position x."""
    frac = (x % gl) / gl
    flipped = 0.25 < frac < 0.75
    if strand == 1:
        return "right" if flipped else "left"
    else:
        return "left" if flipped else "right"


def draw_mito_map(parsed, genome_name="Genome", output_file=None,
                  figsize=(12, 12), dpi=600, min_label_gap=None):
    """Draw the circular mitochondrial genome map."""
    genes = parsed["genes"]
    gc_data = parsed["gc"]
    GL = parsed["genome_length"]

    if min_label_gap is None:
        n = len(genes)
        min_label_gap = max(2500, int(GL / (n * 1.3)))
        min_label_gap = min(min_label_gap, 6000)

    pg = [g for g in genes if g["strand"] == 1]
    mg = [g for g in genes if g["strand"] == -1]
    pp, pm_ = spread_labels([g["mid"] for g in pg], GL, min_label_gap, moved_threshold=4000)
    mp, mm_ = spread_labels([g["mid"] for g in mg], GL, min_label_gap, moved_threshold=4000)

    R_GP = (78, 81)
    R_BB = (77, 78)
    R_GM = (74, 77)
    R_GC = (32, 44)
    # Forward strand leader lines
    R_P_LINE = 84
    R_P_BEND = 82
    # Reverse strand leader lines (extend deeper inward)
    R_M_LINE = 66
    R_M_BEND = 70

    circos = Circos({"genome": GL}, space=0, start=-270, end=90)
    sector = circos.sectors[0]

    # ── Forward strand track ──
    RP_LO, RP_HI = R_GP[0], 100
    tp = sector.add_track((RP_LO, RP_HI))
    for g in pg:
        col = g["color"]
        if g["has_intron"] and len(g["exons"]) >= 2:
            tp.rect(g["start"], g["end"], r_lim=(79, 80), fc=_INTRON_HEX, ec="black", lw=0.2)
            for es, ee in g["exons"]:
                tp.rect(es, ee, r_lim=R_GP, fc=col, ec="black", lw=0.3)
        else:
            tp.rect(g["start"], g["end"], r_lim=R_GP, fc=col, ec="black", lw=0.3)

    for i, g in enumerate(pg):
        gx = g["mid"]
        lx = pp[i]
        moved = pm_[i]
        fs = 7.5 if g["category"] == "trna" else 8 if g["category"] == "rrna" else 8.5
        ha = _label_ha(lx, GL, 1)
        if moved:
            tp.line([gx, gx], [R_GP[1], R_P_BEND], vmin=RP_LO, vmax=RP_HI, lw=0.35, color="#808080")
            tp.line([gx, lx], [R_P_BEND, R_P_LINE], vmin=RP_LO, vmax=RP_HI, lw=0.35, color="#808080")
        else:
            tp.line([gx, lx], [R_GP[1], R_P_LINE], vmin=RP_LO, vmax=RP_HI, lw=0.35, color="#808080")
        tp.text(g["name"], x=lx, r=R_P_LINE + 0.5, size=fs,
                adjust_rotation=True, orientation="vertical",
                fontstyle="italic", fontweight="bold", ha=ha)

    # ── Backbone line ──
    sector.add_track(R_BB).rect(0, GL, fc="black", ec="none")

    # ── Reverse strand track ──
    RM_LO, RM_HI = 46, R_GM[1]
    tm = sector.add_track((RM_LO, RM_HI))
    for g in mg:
        col = g["color"]
        if g["has_intron"] and len(g["exons"]) >= 2:
            tm.rect(g["start"], g["end"], r_lim=(75, 76), fc=_INTRON_HEX, ec="black", lw=0.2)
            for es, ee in g["exons"]:
                tm.rect(es, ee, r_lim=R_GM, fc=col, ec="black", lw=0.3)
        else:
            tm.rect(g["start"], g["end"], r_lim=R_GM, fc=col, ec="black", lw=0.3)

    for i, g in enumerate(mg):
        gx = g["mid"]
        lx = mp[i]
        moved = mm_[i]
        fs = 7.5 if g["category"] == "trna" else 8 if g["category"] == "rrna" else 8.5
        ha = _label_ha(lx, GL, -1)
        if moved:
            tm.line([gx, gx], [R_GM[0], R_M_BEND], vmin=RM_LO, vmax=RM_HI, lw=0.35, color="#808080")
            tm.line([gx, lx], [R_M_BEND, R_M_LINE], vmin=RM_LO, vmax=RM_HI, lw=0.35, color="#808080")
        else:
            tm.line([gx, lx], [R_GM[0], R_M_LINE], vmin=RM_LO, vmax=RM_HI, lw=0.35, color="#808080")
        tm.text(g["name"], x=lx, r=R_M_LINE - 0.5, size=fs,
                adjust_rotation=True, orientation="vertical",
                fontstyle="italic", fontweight="bold", ha=ha)

    # ── GC content ring ──
    gc_vals = [d["gc"] for d in gc_data]
    gc_mean = np.mean(gc_vals)
    gc_min_v, gc_max_v = min(gc_vals) - 0.01, max(gc_vals) + 0.01
    gc_range = gc_max_v - gc_min_v
    gc_h = R_GC[1] - R_GC[0]
    t_gc = sector.add_track(R_GC)
    t_gc.rect(0, GL, fc="#E0E0E0", ec="none")
    for d in gc_data:
        frac = (d["gc"] - gc_min_v) / gc_range
        t_gc.rect(d["start"], d["end"], r_lim=(R_GC[1] - frac * gc_h, R_GC[1]), fc="#9A9A9A", ec="none")
    mean_r = R_GC[1] - (gc_mean - gc_min_v) / gc_range * gc_h
    t_gc.line([0, GL], [mean_r, mean_r], vmin=R_GC[0], vmax=R_GC[1], lw=0.4, color="#444444")

    # ── Render figure ──
    fig = circos.plotfig(figsize=figsize)
    ax = fig.axes[0]
    ax.text(0.5, 0.57, genome_name, transform=ax.transAxes, fontsize=26,
            fontstyle="italic", fontweight="bold", ha="center", va="center")
    ax.text(0.5, 0.51, "mitochondrial genome", transform=ax.transAxes, fontsize=15, ha="center", va="center")
    ax.text(0.5, 0.46, f"{GL:,} bp", transform=ax.transAxes, fontsize=15, ha="center", va="center")
    ax.text(0.5, 0.42, f"GC = {gc_mean * 100:.1f}%", transform=ax.transAxes,
            fontsize=13, ha="center", va="center", color="#555555")
    handles = [mpatches.Patch(fc=c, ec="black", lw=0.5, label=l) for l, c in LEGEND_ITEMS]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.10, -0.13),
              fontsize=9.5, frameon=False, ncol=1, handlelength=1.2, handleheight=1.0, labelspacing=0.35)
    if output_file:
        fig.savefig(output_file, dpi=dpi, bbox_inches="tight", facecolor="white")
        print(f"Saved: {output_file}")
    else:
        plt.show()
    plt.close(fig)


def plot_mito_genome(gb_file, genome_name=None, output_file=None, gc_window=200, **kw):
    """Main entry point: parse GenBank and draw circular genome map."""
    parsed = parse_genbank(gb_file, gc_window=gc_window)
    if genome_name is None:
        genome_name = Path(gb_file).stem
    draw_mito_map(parsed, genome_name=genome_name, output_file=output_file, **kw)
    return parsed
