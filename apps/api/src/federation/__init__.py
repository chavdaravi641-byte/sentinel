"""Phase 6 -- Statewide CCTV Federation & Interoperability Platform.

This package is fully additive. It does not modify any Phase 1-5 module or
router. It exposes its own FastAPI router (``router.py``) and keeps its
configuration, database and models isolated from the main application so that
it can be developed, tested and validated independently.
"""

__version__ = "6.0.0"
