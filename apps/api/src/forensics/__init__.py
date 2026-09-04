"""Forensic evidence module (grand-finale killer feature #1).

Produces court-admissible, tamper-evident vehicle dossiers with a SHA-256
integrity chain over canonicalised JSON so an exported artefact can be
independently re-verified end-to-end.
"""

from src.forensics.dossier import (
    canonical_json,
    compute_integrity,
    DossierSighting,
    ForensicDossier,
    build_dossier,
    render_dossier_markdown,
    render_dossier_pdf,
)

__all__ = [
    "canonical_json",
    "compute_integrity",
    "DossierSighting",
    "ForensicDossier",
    "build_dossier",
    "render_dossier_markdown",
    "render_dossier_pdf",
]
