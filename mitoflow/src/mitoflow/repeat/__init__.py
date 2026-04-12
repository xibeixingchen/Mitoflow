"""Repeat detection modules."""

try:
    from .visualize import plot_all_repeat
except ImportError:
    plot_all_repeat = None
