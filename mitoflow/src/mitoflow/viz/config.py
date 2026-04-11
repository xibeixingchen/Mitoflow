"""Color scheme management for all MitoFlow visualizations.

Centralizes the OGDraw Chondriome color palette used across circular maps,
linear views, synteny diagrams, and other plots. Supports YAML-based
custom color scheme loading.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── OGDraw Chondriome default palette ─────────────────────────────
# RGB tuples (0-255) matching OGDraw's mitochondrial genome coloring
DEFAULT_COLORS: dict[str, tuple[int, int, int]] = {
    # Complex I (NADH dehydrogenase)
    "complex_i": (255, 236, 0),       # yellow
    # Complex II (SDH)
    "complex_ii": (52, 211, 77),      # green
    # Complex III (cob)
    "complex_iii": (200, 250, 40),    # yellow-green
    # Complex IV (cox)
    "complex_iv": (255, 180, 255),    # pink
    # Complex V (ATP synthase)
    "complex_v": (151, 190, 13),      # olive
    # Cytochrome c biogenesis (ccm)
    "ccm": (50, 137, 37),             # dark green
    # Ribosomal proteins SSU (rps)
    "rps": (219, 170, 115),           # tan
    # Ribosomal proteins LSU (rpl)
    "rpl": (158, 119, 66),            # brown
    # Maturases (matR, clp)
    "maturase": (233, 93, 15),        # orange
    # Transport (mttB)
    "transport": (128, 128, 128),     # gray
    # Other CDS
    "other_cds": (171, 37, 157),      # violet
    # ORFs
    "orf": (87, 185, 168),            # teal
    # tRNA
    "trna": (22, 41, 131),            # dark blue
    # rRNA
    "rrna": (226, 0, 26),             # red
    # Intron
    "intron": (255, 255, 255),        # white
    # Repeat
    "repeat": (160, 160, 160),        # grey
    # MTPT (chloroplast-derived)
    "mtpt": (0, 150, 136),            # teal-green
}

CATEGORY_LABELS: dict[str, str] = {
    "complex_i": "Complex I (nad)",
    "complex_ii": "Complex II (sdh)",
    "complex_iii": "Complex III (cob)",
    "complex_iv": "Complex IV (cox)",
    "complex_v": "Complex V (atp)",
    "ccm": "Cytochrome c biogenesis",
    "rps": "Ribosomal proteins (SSU)",
    "rpl": "Ribosomal proteins (LSU)",
    "maturase": "Maturases",
    "transport": "Transport (mttB)",
    "other_cds": "Other protein-coding",
    "orf": "ORFs",
    "trna": "tRNA",
    "rrna": "rRNA",
    "intron": "Intron",
    "repeat": "Repeat",
    "mtpt": "MTPT (chloroplast-derived)",
}

# Gene prefix -> category mapping
GENE_PREFIX_MAP: dict[str, str] = {
    "nad": "complex_i",
    "nd": "complex_i",
    "sdh": "complex_ii",
    "cob": "complex_iii",
    "cox": "complex_iv",
    "atp": "complex_v",
    "ccm": "ccm",
    "ccb": "ccm",
    "rps": "rps",
    "rpl": "rpl",
    "mat": "maturase",
    "clp": "maturase",
    "mtt": "transport",
    "orf": "orf",
    "trn": "trna",
    "rrn": "rrna",
}


@dataclass
class ColorConfig:
    """Centralized color configuration for all MitoFlow visualizations.

    Provides consistent color assignment across all plot types.
    Supports custom overrides and YAML-based scheme loading.
    """
    scheme: str = "ogdraw"
    colors: dict[str, tuple[int, int, int]] = field(default_factory=lambda: dict(DEFAULT_COLORS))

    def get_rgb01(self, category: str) -> tuple[float, float, float]:
        """Get RGB tuple in 0-1 range (for matplotlib)."""
        rgb = self.colors.get(category, DEFAULT_COLORS.get("other_cds", (171, 37, 157)))
        return (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

    def get_hex(self, category: str) -> str:
        """Get hex color string (e.g. '#ffec00')."""
        rgb = self.colors.get(category, DEFAULT_COLORS.get("other_cds", (171, 37, 157)))
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def get_rgb255(self, category: str) -> tuple[int, int, int]:
        """Get RGB tuple in 0-255 range."""
        return self.colors.get(category, DEFAULT_COLORS.get("other_cds", (171, 37, 157)))

    def classify_gene(self, gene_name: str, gene_type: str = "CDS") -> str:
        """Classify a gene into a functional category for coloring."""
        name_lower = gene_name.lower().strip()

        if gene_type == "tRNA" or name_lower.startswith("trn"):
            return "trna"
        if gene_type == "rRNA" or name_lower in {"rrn5", "rrn18", "rrn26", "rrn5s", "rrn18s", "rrn26s"}:
            return "rrna"

        for prefix, category in GENE_PREFIX_MAP.items():
            if name_lower.startswith(prefix):
                return category

        if name_lower == "mttb":
            return "transport"
        if name_lower == "matr":
            return "maturase"

        return "other_cds"

    def gene_color_hex(self, gene_name: str, gene_type: str = "CDS") -> str:
        """Get hex color for a gene by name."""
        return self.get_hex(self.classify_gene(gene_name, gene_type))

    def gene_color_rgb01(self, gene_name: str, gene_type: str = "CDS") -> tuple[float, float, float]:
        """Get RGB 0-1 color for a gene by name."""
        return self.get_rgb01(self.classify_gene(gene_name, gene_type))

    def load_yaml(self, yaml_path: Path) -> None:
        """Load custom color scheme from YAML file.

        YAML format:
        ```yaml
        scheme: custom
        colors:
          complex_i: [255, 236, 0]
          complex_ii: [52, 211, 77]
          ...
        ```
        """
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed. Install with: pip install pyyaml")
            return

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        if "scheme" in data:
            self.scheme = data["scheme"]
        if "colors" in data:
            for cat, color in data["colors"].items():
                if isinstance(color, list) and len(color) == 3:
                    self.colors[cat] = tuple(int(c) for c in color)

        logger.info(f"Loaded color scheme '{self.scheme}' from {yaml_path}")

    def save_yaml(self, yaml_path: Path) -> None:
        """Save current color scheme to YAML file."""
        try:
            import yaml
        except ImportError:
            # Fallback: write manually
            lines = [f"scheme: {self.scheme}", "colors:"]
            for cat, rgb in sorted(self.colors.items()):
                lines.append(f"  {cat}: [{rgb[0]}, {rgb[1]}, {rgb[2]}]")
            yaml_path = Path(yaml_path)
            yaml_path.write_text("\n".join(lines) + "\n")
            return

        data = {
            "scheme": self.scheme,
            "colors": {cat: list(rgb) for cat, rgb in sorted(self.colors.items())},
        }
        yaml_path = Path(yaml_path)
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=True)
        logger.info(f"Color scheme saved to {yaml_path}")


def get_default_config() -> ColorConfig:
    """Get the default OGDraw-style color configuration."""
    return ColorConfig()
