"""HTML report generation for CMS analysis.

Generates a standalone HTML report with embedded CSS and inline
matplotlib base64-encoded images showing summary statistics, a sortable
candidate table, score breakdown charts, and chimera structure diagrams.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from .predictor import CMSResult

logger = logging.getLogger(__name__)


# ── Inline plot helpers ──────────────────────────────────────────────

def _fig_to_base64(fig: plt.Figure) -> str:
    """Render a matplotlib figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _make_score_chart(result: "CMSResult") -> str:
    """Build a horizontal stacked-bar chart and return as base64 PNG."""
    candidates = result.candidates[:20]
    if not candidates:
        return ""

    labels = [c.orf_id for c in candidates]
    weights = {"chimera": 0.30, "tm": 0.25, "homolog": 0.20,
               "context": 0.15, "length": 0.10}
    colors = {"chimera": "#e74c3c", "tm": "#3498db", "homolog": "#2ecc71",
              "context": "#f39c12", "length": "#9b59b6"}

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.35 + 1)))
    y = np.zeros(len(labels))
    for dim in ("chimera", "tm", "homolog", "context", "length"):
        vals = np.array([getattr(c, f"{dim}_score") for c in candidates]) * weights[dim]
        ax.barh(labels, vals, left=y, color=colors[dim], label=dim.capitalize(),
                edgecolor="white", linewidth=0.5)
        y += vals

    ax.set_xlabel("Weighted Score")
    ax.set_title("Score Breakdown (Top Candidates)")
    ax.legend(loc="lower right", fontsize=8)
    ax.invert_yaxis()
    plt.tight_layout()
    return _fig_to_base64(fig)


def _make_confidence_pie(result: "CMSResult") -> str:
    """Build a confidence-level pie chart and return as base64 PNG."""
    sizes = [result.high_confidence, result.medium_confidence,
             result.n_candidates - result.high_confidence - result.medium_confidence]
    if sum(sizes) == 0:
        return ""
    labels = ["High", "Medium", "Low"]
    colors = ["#e74c3c", "#f39c12", "#95a5a6"]
    # Filter out zero slices
    filtered = [(s, l, c) for s, l, c in zip(sizes, labels, colors) if s > 0]
    sizes_f, labels_f, colors_f = zip(*filtered)

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes_f, labels=labels_f, colors=colors_f, autopct="%1.0f%%",
           startangle=90, textprops={"fontsize": 10})
    ax.set_title("Confidence Distribution")
    plt.tight_layout()
    return _fig_to_base64(fig)


# ── HTML Template ────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} - CMS Analysis Report</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    margin: 0; padding: 20px;
    background: #f8f9fa; color: #2c3e50;
}}
h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
h2 {{ color: #34495e; margin-top: 30px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin: 20px 0;
}}
.stat-card {{
    background: white; border-radius: 8px; padding: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;
}}
.stat-card .value {{ font-size: 2em; font-weight: bold; color: #3498db; }}
.stat-card .label {{ font-size: 0.85em; color: #7f8c8d; }}
.charts {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    margin: 20px 0;
}}
.charts img {{ width: 100%; border-radius: 8px; }}
table {{
    width: 100%; border-collapse: collapse; background: white;
    border-radius: 8px; overflow: hidden;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
th {{ background: #34495e; color: white; cursor: pointer; user-select: none; }}
th:hover {{ background: #2c3e50; }}
th.sort-asc::after {{ content: " \\25B2"; }}
th.sort-desc::after {{ content: " \\25BC"; }}
tr:hover {{ background: #f1f8ff; }}
.badge {{
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 0.8em; font-weight: bold; color: white;
}}
.badge-high {{ background: #e74c3c; }}
.badge-medium {{ background: #f39c12; }}
.badge-low {{ background: #95a5a6; }}
.footer {{
    margin-top: 40px; text-align: center; color: #95a5a6;
    font-size: 0.85em; border-top: 1px solid #ecf0f1; padding-top: 16px;
}}
</style>
</head>
<body>
<div class="container">
<h1>{name} - CMS Analysis Report</h1>

<div class="stats">
  <div class="stat-card">
    <div class="value">{total_orfs}</div>
    <div class="label">ORFs Scanned</div>
  </div>
  <div class="stat-card">
    <div class="value">{orfs_filtered}</div>
    <div class="label">ORFs After Filter</div>
  </div>
  <div class="stat-card">
    <div class="value">{n_candidates}</div>
    <div class="label">CMS Candidates</div>
  </div>
  <div class="stat-card">
    <div class="value" style="color:#e74c3c">{n_high}</div>
    <div class="label">High Confidence</div>
  </div>
  <div class="stat-card">
    <div class="value" style="color:#f39c12">{n_medium}</div>
    <div class="label">Medium Confidence</div>
  </div>
</div>

<h2>Score Breakdown</h2>
<div class="charts">
  <img src="data:image/png;base64,{score_chart}" alt="Score breakdown">
  <img src="data:image/png;base64,{pie_chart}" alt="Confidence distribution">
</div>

<h2>Candidate Table</h2>
<table id="candidate-table">
<thead>
<tr>
  <th data-sort="int" data-col="0">Rank</th>
  <th data-sort="str" data-col="1">ORF ID</th>
  <th data-sort="int" data-col="2">Start</th>
  <th data-sort="int" data-col="3">End</th>
  <th data-sort="str" data-col="4">Strand</th>
  <th data-sort="int" data-col="5">Length (aa)</th>
  <th data-sort="float" data-col="6">Total Score</th>
  <th data-sort="str" data-col="7">Confidence</th>
  <th data-sort="float" data-col="8">Chimera</th>
  <th data-sort="float" data-col="9">TM</th>
  <th data-sort="float" data-col="10">Homolog</th>
  <th data-sort="float" data-col="11">Context</th>
  <th data-sort="float" data-col="12">Length</th>
  <th data-sort="int" data-col="13">TM#</th>
  <th data-sort="str" data-col="14">CMS Homolog</th>
  <th data-sort="str" data-col="15">Chimera Sources</th>
  <th data-sort="str" data-col="16">Nearby Genes</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>

<div class="footer">
  Generated by MitoFlow CMS Analysis &middot; {timestamp}
</div>
</div>

<script>
(function() {{
  const table = document.getElementById("candidate-table");
  const headers = table.querySelectorAll("th");
  let sortCol = -1, sortAsc = true;

  headers.forEach(function(th) {{
    th.addEventListener("click", function() {{
      const col = parseInt(th.dataset.col);
      if (sortCol === col) {{ sortAsc = !sortAsc; }} else {{ sortCol = col; sortAsc = true; }}
      // Update header classes
      headers.forEach(function(h) {{ h.classList.remove("sort-asc","sort-desc"); }});
      th.classList.add(sortAsc ? "sort-asc" : "sort-desc");

      const tbody = table.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const type = th.dataset.sort;

      rows.sort(function(a, b) {{
        let va = a.children[col].textContent.trim();
        let vb = b.children[col].textContent.trim();
        if (type === "int") {{ va = parseInt(va)||0; vb = parseInt(vb)||0; }}
        else if (type === "float") {{ va = parseFloat(va)||0; vb = parseFloat(vb)||0; }}
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
      }});
      rows.forEach(function(r) {{ tbody.appendChild(r); }});
    }});
  }});
}})();
</script>
</body>
</html>
"""


# ── Public API ───────────────────────────────────────────────────────

def generate_cms_html_report(
    result: "CMSResult",
    output_path: str | Path,
    genome_length: int = 0,
    name: str = "MitoFlow",
) -> Path:
    """Generate a standalone HTML report with embedded CSS/JS.

    The report includes:
    - Summary statistics cards
    - Candidate table (sortable by clicking column headers)
    - Score breakdown chart (inline matplotlib base64)
    - Confidence distribution pie chart

    Args:
        result: CMSResult from prediction.
        output_path: Destination HTML file path.
        genome_length: Genome length (used in header, 0 = unknown).
        name: Project/species name.

    Returns:
        Path to the saved HTML file.
    """
    from datetime import datetime

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build inline chart images
    score_chart_b64 = _make_score_chart(result)
    pie_chart_b64 = _make_confidence_pie(result)

    # Build table rows
    rows_html = []
    for rank, c in enumerate(result.candidates, 1):
        conf_class = c.confidence.lower()
        sources = ", ".join(c.chimera.source_genes) if c.chimera else "-"
        nearby = ", ".join(c.nearby_genes) if c.nearby_genes else "-"
        homolog = c.cms_homolog or "-"

        rows_html.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<td>{c.orf_id}</td>"
            f"<td>{c.start:,}</td>"
            f"<td>{c.end:,}</td>"
            f"<td>{'+' if c.strand == 1 else '-'}</td>"
            f"<td>{c.length_aa}</td>"
            f"<td>{c.total_score:.1f}</td>"
            f'<td><span class="badge badge-{conf_class}">{c.confidence}</span></td>'
            f"<td>{c.chimera_score:.1f}</td>"
            f"<td>{c.tm_score:.1f}</td>"
            f"<td>{c.homolog_score:.1f}</td>"
            f"<td>{c.context_score:.1f}</td>"
            f"<td>{c.length_score:.1f}</td>"
            f"<td>{c.n_tm_domains}</td>"
            f"<td>{homolog}</td>"
            f"<td>{sources}</td>"
            f"<td>{nearby}</td>"
            f"</tr>"
        )

    html = _HTML_TEMPLATE.format(
        name=name,
        total_orfs=result.total_orfs_scanned,
        orfs_filtered=result.orfs_after_filter,
        n_candidates=result.n_candidates,
        n_high=result.high_confidence,
        n_medium=result.medium_confidence,
        score_chart=score_chart_b64,
        pie_chart=pie_chart_b64,
        table_rows="\n".join(rows_html),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    output_path.write_text(html, encoding="utf-8")
    logger.info(f"CMS HTML report saved to {output_path}")
    return output_path
