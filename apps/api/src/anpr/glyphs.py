"""Shared 5x7 glyph font + render/match helpers for ANPR simulation.

Used by both the synthetic dataset generator (to render plates) and the sim OCR
stage (to read them back via template matching). Sharing the font keeps the
controlled experiment self-consistent so character/word accuracy are meaningful
and reproducible. Not used by the real (PaddleOCR / ONNX) path.
"""

from __future__ import annotations


import numpy as np

_GLYPHS: dict[str, list[str]] = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
GLYPH_W, GLYPH_H = 5, 7

# Visually-confusable glyph pairs the OCR post-processor may swap.
CONFUSABLES: dict[str, str] = {"O": "0", "I": "1", "B": "8", "S": "5"}
CONFUSABLE_INV: dict[str, str] = {v: k for k, v in CONFUSABLES.items()}


def alphabets() -> list[str]:
    return list(_ALPHABET)


def glyph(ch: str) -> list[str]:
    """Return the 5x7 bitmap rows for a character ('' if unsupported)."""
    return _GLYPHS.get(ch.upper(), [])


def render_glyph(ch: str, scale: int = 1, on: int = 255, off: int = 0) -> np.ndarray:
    """Render a character as a binary HxW uint8 glyph image."""
    rows = glyph(ch)
    if not rows:
        rows = [["0"] * GLYPH_W for _ in range(GLYPH_H)]
    h = GLYPH_H * scale
    w = GLYPH_W * scale
    img = np.full((h, w), off, dtype=np.uint8)
    for r, row in enumerate(rows):
        for c, lit in enumerate(row):
            if lit == "1":
                img[r * scale : (r + 1) * scale, c * scale : (c + 1) * scale] = on
    return img


def paint_glyph(canvas, glyph_rows: list[str], x0: int, y0: int, scale: int, color) -> None:
    for r, row in enumerate(glyph_rows):
        for c, lit in enumerate(row):
            if lit == "1":
                canvas[y0 + r * scale : y0 + (r + 1) * scale,
                       x0 + c * scale : x0 + (c + 1) * scale] = color


def glyph_lib():
    """Return {char: binary 5x7 uint8 template} for all supported characters."""
    return {ch: (np.asarray([list(r) for r in glyph(ch)], dtype=np.uint8) * 255)
            for ch in _ALPHABET}


__all__ = [
    "_GLYPHS", "alphabets", "glyph", "render_glyph", "paint_glyph",
    "glyph_lib", "CONFUSABLES", "CONFUSABLE_INV", "GLYPH_W", "GLYPH_H",
]
