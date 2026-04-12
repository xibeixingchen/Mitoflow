"""HTML report generator for MitoFlow analysis results.

Generates a self-contained interactive HTML report with:
- Circular genome map (OGDrawR or pycirclize)
- QC scores and radar chart
- Gene annotation summary table
- Gene completeness matrix
- CMS candidates table
- Download links for all output files
"""

from __future__ import annotations
import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReportData:
    """Data to include in the report."""
    project_name: str = "MitoFlow"
    genome_length: int = 0
    gc_content: float = 0.0
    n_contigs: int = 1

    # Annotation stats
    n_pcg: int = 0
    n_trna: int = 0
    n_rrna: int = 0
    gene_list: list = field(default_factory=list)  # [{name, type, start, end, strand, product}]

    # QC scores
    qc_overall: float = 0.0
    qc_grade: str = "N/A"
    qc_completeness: float = 0.0
    qc_contiguity: float = 0.0
    qc_correctness: float = 0.0
    qc_contamination: float = 0.0
    qc_structure: float = 0.0
    qc_missing_genes: list = field(default_factory=list)
    qc_passed: bool = True

    # CMS
    cms_candidates: list = field(default_factory=list)  # [{orf_id, score, confidence, ...}]

    # File links
    output_files: dict = field(default_factory=dict)


def generate_html_report(
    data: ReportData,
    output_path: Path,
    gb_path: Optional[Path] = None,
) -> Path:
    """Generate a self-contained HTML report.

    Args:
        data: ReportData with all analysis results.
        output_path: Output HTML file path.
        gb_path: Optional path to GenBank file for generating circos plot.

    Returns:
        Path to generated HTML file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Pre-compute values for template
    qc_pass_class = "pass" if data.qc_passed else "fail"
    
    # Generate circos plot if GenBank provided
    circos_b64 = ""
    if gb_path and gb_path.exists():
        try:
            circos_png = generate_circos_plot(gb_path, output_path.parent, data.project_name)
            if circos_png and circos_png.exists():
                circos_b64 = encode_image_to_base64(circos_png)
        except Exception as e:
            logger.warning(f"Failed to generate circos plot: {e}")

    html = _build_html(data, qc_pass_class, circos_b64)
    output_path.write_text(html, encoding="utf-8")

    logger.info(f"HTML report generated: {output_path}")
    return output_path


def _build_html(data: ReportData, qc_pass_class: str = "pass", circos_image_b64: str = "") -> str:
    """Build complete HTML report string."""
    circos_section = _circos_section_html(circos_image_b64) if circos_image_b64 else ""
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{data.project_name} — MitoFlow Report</title>
<style>
{_css()}
</style>
</head>
<body>
<div class="container">
<header>
<h1>{data.project_name}</h1>
<p class="subtitle">MitoFlow — Plant Mitochondrial Genome Analysis Report</p>
</header>

{circos_section}

<section class="overview">
<h2>Genome Overview</h2>
<div class="stat-grid">
<div class="stat-card">
<span class="stat-value">{data.genome_length:,}</span>
<span class="stat-label">Genome Size (bp)</span>
</div>
<div class="stat-card">
<span class="stat-value">{data.gc_content:.1f}%</span>
<span class="stat-label">GC Content</span>
</div>
<div class="stat-card">
<span class="stat-value">{data.n_contigs}</span>
<span class="stat-label">Contigs</span>
</div>
<div class="stat-card">
<span class="stat-value">{data.n_pcg}</span>
<span class="stat-label">Protein Genes</span>
</div>
<div class="stat-card">
<span class="stat-value">{data.n_trna}</span>
<span class="stat-label">tRNA Genes</span>
</div>
<div class="stat-card">
<span class="stat-value">{data.n_rrna}</span>
<span class="stat-label">rRNA Genes</span>
</div>
</div>
</section>

<section class="qc">
<h2>QC Assessment</h2>
<div class="qc-summary">
<div class="qc-score {qc_pass_class}">
<span class="score-value">{data.qc_overall:.0f}</span>
<span class="score-grade">{data.qc_grade}</span>
<span class="score-label">Overall Score</span>
</div>
<div class="qc-dims">
{_qc_bars(data)}
</div>
</div>
{_missing_genes_html(data)}
</section>

<section class="genes">
<h2>Gene Annotations</h2>
<div class="table-controls">
<input type="text" id="gene-search" placeholder="Search genes..." onkeyup="filterGenes()">
</div>
<div class="table-wrapper">
<table id="gene-table">
<thead>
<tr><th>Gene</th><th>Type</th><th>Start</th><th>End</th><th>Strand</th><th>Product</th></tr>
</thead>
<tbody>
{_gene_table_rows(data)}
</tbody>
</table>
</div>
</section>

{_cms_section(data)}

<section class="files">
<h2>Output Files</h2>
<ul class="file-list">
{_file_links(data)}
</ul>
</section>

<footer>
<p>Generated by <strong>MitoFlow v0.1.0</strong> — One command, one paper.</p>
</footer>
</div>

<script>
{_javascript()}
</script>
</body>
</html>"""


def _circos_section_html(image_b64: str) -> str:
    """Generate HTML for circos plot section with colors from centralized config."""
    from ..viz.config import ColorConfig, CATEGORY_LABELS
    cc = ColorConfig()
    legend_items = []
    for category, label in CATEGORY_LABELS.items():
        hex_color = cc.get_hex(category)
        legend_items.append(
            f'<div class="legend-item">'
            f'<span class="legend-color" style="background:{hex_color}"></span>'
            f'{label}</div>'
        )
    legend_html = "\n".join(legend_items)
    return f"""
<section class="circos">
<h2>Genome Map</h2>
<div class="circos-container">
<img src="{image_b64}" alt="Circular Genome Map" class="circos-image">
<div class="circos-legend">
{legend_html}
</div>
</div>
<p class="circos-note">Outer track: forward strand (+) | Inner track: reverse strand (-)</p>
</section>
"""


def _css() -> str:
    return """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f7fa; color: #333; line-height: 1.6; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
header { text-align: center; padding: 30px 0; border-bottom: 2px solid #4CAF50; margin-bottom: 30px; }
header h1 { color: #2c3e50; font-size: 2.2em; }
.subtitle { color: #7f8c8d; font-size: 1.1em; margin-top: 5px; }
section { background: white; border-radius: 8px; padding: 25px; margin-bottom: 20px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
h2 { color: #2c3e50; margin-bottom: 15px; padding-bottom: 8px; border-bottom: 1px solid #eee; }

/* Circos plot styles */
.circos-container { display: flex; align-items: center; justify-content: center; gap: 30px; flex-wrap: wrap; }
.circos-image { max-width: 500px; width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
.circos-legend { display: grid; grid-template-columns: 1fr; gap: 8px; font-size: 0.9em; }
.legend-item { display: flex; align-items: center; gap: 8px; }
.legend-color { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #ccc; }
.circos-note { text-align: center; color: #666; font-size: 0.85em; margin-top: 15px; font-style: italic; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
.stat-card { background: #f8f9fa; border-radius: 8px; padding: 15px; text-align: center; }
.stat-value { display: block; font-size: 1.8em; font-weight: bold; color: #4CAF50; }
.stat-label { display: block; font-size: 0.85em; color: #7f8c8d; margin-top: 4px; }
.qc-summary { display: flex; gap: 30px; align-items: center; flex-wrap: wrap; }
.qc-score { text-align: center; padding: 20px; border-radius: 12px; min-width: 150px; }
.qc-score.pass { background: #e8f5e9; }
.qc-score.fail { background: #ffebee; }
.score-value { display: block; font-size: 3em; font-weight: bold; color: #4CAF50; }
.qc-score.fail .score-value { color: #f44336; }
.score-grade { display: block; font-size: 1.5em; font-weight: bold; margin-top: 5px; }
.score-label { display: block; font-size: 0.9em; color: #7f8c8d; }
.qc-dims { flex: 1; min-width: 300px; }
.qc-bar { margin-bottom: 10px; }
.qc-bar-label { display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 3px; }
.qc-bar-track { background: #eee; border-radius: 4px; height: 12px; overflow: hidden; }
.qc-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
.table-controls { margin-bottom: 15px; }
.table-controls input { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;
                        font-size: 0.95em; }
.table-wrapper { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
th { background: #4CAF50; color: white; padding: 10px 8px; text-align: left; position: sticky; top: 0; }
td { padding: 8px; border-bottom: 1px solid #eee; }
tr:hover { background: #f5f5f5; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
.badge-cds { background: #e3f2fd; color: #1565c0; }
.badge-trna { background: #f3e5f5; color: #7b1fa2; }
.badge-rrna { background: #fce4ec; color: #c62828; }
.missing-genes { background: #fff3e0; padding: 12px; border-radius: 6px; margin-top: 15px; }
.missing-genes ul { margin-left: 20px; }
.file-list { list-style: none; }
.file-list li { padding: 8px 0; border-bottom: 1px solid #eee; }
.file-list a { color: #1976d2; text-decoration: none; }
.file-list a:hover { text-decoration: underline; }
footer { text-align: center; padding: 20px; color: #999; font-size: 0.9em; }
.cms-table td:first-child { font-weight: bold; }
.high { color: #4CAF50; font-weight: bold; }
.medium { color: #FF9800; font-weight: bold; }
.low { color: #9E9E9E; }
"""


def _qc_bars(data: ReportData) -> str:
    dims = [
        ("Completeness", data.qc_completeness),
        ("Contiguity", data.qc_contiguity),
        ("Correctness", data.qc_correctness),
        ("Contamination", data.qc_contamination),
        ("Structure", data.qc_structure),
    ]
    bars = []
    for name, score in dims:
        color = "#4CAF50" if score >= 75 else "#FF9800" if score >= 50 else "#f44336"
        bars.append(f"""
        <div class="qc-bar">
            <div class="qc-bar-label"><span>{name}</span><span>{score:.0f}/100</span></div>
            <div class="qc-bar-track"><div class="qc-bar-fill" style="width:{score}%;background:{color}"></div></div>
        </div>""")
    return "\n".join(bars)


def _missing_genes_html(data: ReportData) -> str:
    if not data.qc_missing_genes:
        return ""
    items = "".join(f"<li>{g}</li>" for g in data.qc_missing_genes)
    return f"""<div class="missing-genes">
<strong>Missing core genes:</strong>
<ul>{items}</ul></div>"""


def _gene_table_rows(data: ReportData) -> str:
    rows = []
    for g in data.gene_list:
        gtype = g.get("type", "CDS")
        badge_class = {"CDS": "badge-cds", "tRNA": "badge-trna", "rRNA": "badge-rrna"}.get(gtype, "badge-cds")
        rows.append(
            f"""<tr data-gene="{g.get('name', '').lower()}">
<td>{g.get('name', '')}</td>
<td><span class="badge {badge_class}">{gtype}</span></td>
<td>{g.get('start', 0):,}</td>
<td>{g.get('end', 0):,}</td>
<td>{'+' if g.get('strand', 1) == 1 else '-'}</td>
<td>{g.get('product', '')}</td>
</tr>"""
        )
    return "\n".join(rows)


def _cms_section(data: ReportData) -> str:
    if not data.cms_candidates:
        return ""
    rows = []
    for c in data.cms_candidates:
        conf_class = c.get("confidence", "Low").lower()
        rows.append(
            f"""<tr>
<td>{c.get('orf_id', '')}</td>
<td class="{conf_class}">{c.get('total_score', 0):.1f}</td>
<td class="{conf_class}">{c.get('confidence', '')}</td>
<td>{c.get('length_aa', 0)}</td>
<td>{c.get('n_tm', 0)}</td>
<td>{c.get('chimera_sources', '-')}</td>
<td>{c.get('cms_homolog', '-')}</td>
</tr>"""
        )
    return f"""
<section class="cms">
<h2>CMS Candidates</h2>
<div class="table-wrapper">
<table class="cms-table">
<thead><tr><th>ORF</th><th>Score</th><th>Confidence</th><th>Length(aa)</th>
<th>TMs</th><th>Chimera Sources</th><th>CMS Homolog</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
</section>"""


def _file_links(data: ReportData) -> str:
    items = []
    for ftype, fpath in data.output_files.items():
        items.append(f'<li>{ftype}: <a href="{fpath}">{fpath}</a></li>')
    return "\n".join(items)


def _javascript() -> str:
    return """
function filterGenes() {
    var input = document.getElementById('gene-search');
    var filter = input.value.toLowerCase();
    var table = document.getElementById('gene-table');
    var rows = table.getElementsByTagName('tr');
    for (var i = 1; i < rows.length; i++) {
        var gene = rows[i].getAttribute('data-gene') || '';
        rows[i].style.display = gene.includes(filter) ? '' : 'none';
    }
}
"""


def generate_circos_plot(gb_path: Path, output_dir: Path, name: str) -> Optional[Path]:
    """Generate circular genome map using OGDrawR (R, preferred) or gbdraw (Python, fallback).

    Args:
        gb_path: Path to GenBank file
        output_dir: Output directory for plot
        name: Organism name

    Returns:
        Path to generated PNG file or None if failed
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}_circos.png"

    # Try OGDrawR (R) first
    try:
        from ..viz.circos_plot_ogdraw import draw_genome_map, check_ogdrawr_available
        if check_ogdrawr_available():
            result = draw_genome_map(
                genbank_path=gb_path,
                output_path=output_path,
                organism=name,
            )
            if result and result.exists():
                logger.info(f"Genome map generated with OGDrawR (R): {result}")
                return result
            else:
                logger.warning("OGDrawR (R) ran but produced no output file")
        else:
            logger.info("OGDrawR not available, trying gbdraw (Python)")
    except Exception as e:
        logger.warning(f"OGDrawR (R) failed: {e}")

    # Fallback to gbdraw (Python)
    try:
        from ..viz.gbdraw_plot import draw_with_gbdraw, check_gbdraw_available
        if check_gbdraw_available():
            result = draw_with_gbdraw(
                genbank_path=str(gb_path),
                output_path=str(output_path),
                organism=name,
                format="png",
            )
            if output_path.exists():
                logger.info(f"Genome map generated with gbdraw (Python): {output_path}")
                return output_path
        else:
            logger.error("Neither OGDrawR (R) nor gbdraw (Python) available for genome visualization")
    except Exception as e:
        logger.error(f"gbdraw (Python) failed: {e}")
    except Exception as e:
        logger.error(f"OGDrawR (R) failed: {e}")

    return None


def encode_image_to_base64(image_path: Path) -> str:
    """Encode image file to base64 string for embedding in HTML."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    ext = image_path.suffix.lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/svg+xml"
    return f"data:{mime_type};base64,{encoded}"
