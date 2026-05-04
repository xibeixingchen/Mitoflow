"""LLM Wiki — structured knowledge base for plant organelle genomics."""

from .wiki_index import WikiIndex
from .wiki_tools import register_wiki_tools

__all__ = ["WikiIndex", "register_wiki_tools"]
