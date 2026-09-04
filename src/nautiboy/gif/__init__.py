"""Bounded animated GIF decoding and playback scheduling."""

from .decoder import GifDocument, GifLimits, GifProcessingError, inspect_gif

__all__ = ["GifDocument", "GifLimits", "GifProcessingError", "inspect_gif"]
