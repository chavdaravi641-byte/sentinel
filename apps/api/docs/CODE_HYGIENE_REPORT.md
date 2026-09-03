# Code Hygiene Report — Ruff Cleanup (F601 duplicate dict keys)

## Objective
Resolve the remaining Ruff warnings — specifically **F601** (duplicate
dictionary key literal) in `_CONFUSABLE_PAIRS` — **without changing runtime
behavior**. No suppression, no `noqa`, no rule ignores.

## Pre-cleanup state
`ruff check` reported 2 × F601 in `src/anpr/validator.py:43-44`:

```
43 |     "Q": "0", "0": "Q",
44 |     "D": "0", "0": "D",
```

The `"0"` key was declared three times (once in the `"O": "0"` pair on line 37,
and again on lines 43 and 44). In Python, the **last** assignment wins, so the
effective runtime mapping for `"0"` was already `"D"`; the intermediate
`"0": "Q"` entry was dead (overridden) and tripped Ruff.

## Change made
`src/anpr/validator.py` — rewrote `_CONFUSABLE_PAIRS` to use exactly one
canonical entry per key, preserving the identical effective mapping:

**Before (effective, last-wins):**
```python
_CONFUSABLE_PAIRS = {
    "O": "0", "0": "D",
    "I": "1", "1": "I",
    "B": "8", "8": "B",
    "S": "5", "5": "S",
    "Z": "2", "2": "Z",
    "G": "6", "6": "G",
    "Q": "0",
    "D": "0",
}
```

**After (single canonical entry per key):**
```python
_CONFUSABLE_PAIRS: dict[str, str] = {
    "O": "0", "0": "D",
    "I": "1", "1": "I",
    "B": "8", "8": "B",
    "S": "5", "5": "S",
    "Z": "2", "2": "Z",
    "G": "6", "6": "G",
    "Q": "0",
    "D": "0",
}
```

### Why this is behavior-identical
- All key→value pairs in the effective (last-wins-resolved) dictionary are
  preserved exactly: `"0"→"D"`, `"Q"→"0"`, `"D"→"0"`, and every other pair.
- `_CONFUSABLE_PAIRS` is only accessed via `ch in _CONFUSABLE_PAIRS` (membership)
  and `_CONFUSABLE_PAIRS[ch]` (lookup) in `_resolve_char` / the re-ranker; both
  return identical results.
- The removed `"0": "Q"` entry was previously unreachable (overridden by
  `"0": "D"`), so no code path could ever observe it.

No other files changed.

## Validation
| Check | Command | Result |
|-------|---------|--------|
| Ruff | `ruff check src/anpr/validator.py src/anpr/rto_data.py` | **All checks passed!** (0 issues) |
| Full test suite | `python -m pytest -q` | **185 passed** |

## Result
- **Zero Ruff issues.**
- **185/185 tests passing** (unchanged from pre-cleanup).
- Runtime behavior identical; no test expectations altered.
