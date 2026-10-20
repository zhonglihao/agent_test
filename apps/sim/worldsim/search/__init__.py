"""Pluggable free SearchProvider stack (S2 autonomous learning)."""

from .providers import (
    DuckDuckGoProvider,
    SearchHit,
    SearchProvider,
    build_search_stack,
)

__all__ = [
    "DuckDuckGoProvider",
    "SearchHit",
    "SearchProvider",
    "build_search_stack",
]
