"""Metadata resolution components for ArrTheAudio.

This package contains modules for extracting and resolving media metadata
from various sources (Arr apps, TMDB, filename heuristics).
"""

from arrtheaudio.metadata.arr import ArrMetadataParser

__all__ = ["ArrMetadataParser"]
