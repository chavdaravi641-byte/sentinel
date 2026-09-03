# Sentinel AI — Phase 2 Validation Report (Streaming Engine)

**Date:** 2026-08-31
**Environment:** Docker Desktop (Windows, linux/amd64 containers)
**Stack:** `sentinel-ai-api` (FastAPI, Python 3.12) · `sentinel-ai-web` (Next.js 16) · `sentinel-mediamtx` · `postgres:16-alpine` · `redis:7-alpine`
**Validation mode:** full browser-equivalent path — all media traffic exercised through the Next.js origin (`http://localhost:3000/api/*` rewrite proxy); the HLS chain was additionally validated directly against mediamtx (`:8888`) to bisect the proxy layer.

> Host port note: a local PostgreSQL occupies `5432`, so the stack is brought up with `POSTGRES_PORT=5433` (compose already supports this override).

---

## 1. Results summary

| # | Check | Result |
|---|-------|--------|
| 1 | Compose build (api + web) | ✅ Pass |
| 2 | Compose stack starts (`up -d`) | ✅ Pass |
| 3 | All containers healthy (api / web / mediamtx / postgres / redis) | ✅ Pass |
| 4 | Alembic migrations + idempotent seed (17 cameras, no dupes) | ✅ Pass |
| 5 | pytest integration suite (lavfi lifecycle – 4 tests) | ✅ Pass |
| 6 | Start stream → running, live frames (fps > 0, sub-second latency) | ✅ Pass |
| 7 | HLS chain through proxy: master → variant → `.ts` segment (all 200) | ✅ Pass |
| 8 | HLS chain directly against mediamtx × 5 iterations (all 200) | ✅ Pass |
| 9 | Signed snapshot endpoint → valid JPEG | ✅ Pass |
| 10 | Recording lifecycle (start → file → stop → finalized in list) | ✅ Pass |
| 11 | Unauthenticated / unsigned media access rejected | ✅ Pass |
| 12 | Web lint + typecheck clean | ✅ Pass |
| 13 | Live Wall route `/live` renders (200) + sidebar nav wired | ✅ Pass |

**Overall: PASS.** See §4 for one design correction (session pinning removed) and §5 for a known mediamtx sliding-window behavior that is non-blocking for real players.

---

## 2. Stack & infrastructure

| Container | Image | Status | Notes |
|-----------|-------|--------|-------|
| `sentinel-api` | `sentinel-ai-api:latest` | Up | `Application startup complete`; no errors during sustained media traffic. |
| `sentinel-web` | `sentinel-ai-web:latest` | Up | `✓ Ready`; serves `/app`, `/app/*`, and `/live`. |
| `sentinel-mediamtx` | `bluenviron/mediamtx` | Up | HLS `:8888`, WHEP `:8889`, RTSP ingest `:8554`. `hlsAlwaysRemux`, `hlsVariant: mpegts`, `hlsSegmentCount: 15`. |
| `sentinel-postgres` | `postgres:16-alpine` | healthy | `pg_isready` green. |
| `sentinel-redis` | `redis:7-alpine` | healthy | `redis-cli ping` green. |

- Host entrypoints: `3000→3000` (web/proxy). API `8000` is internal-bridge-only; the browser reaches the API exclusively via the Next rewrite proxy.
- Test camera: `TEST-LAVFI-01`, `lavfi://testsrc2=size=1280x720:rate=25`, id `00920543-1b93-4e75-b4e2-40521907396a`.

## 3. Streaming engine lifecycle — integration suite

`apps/api/tests/test_stream_integration.py` (run inside `sentinel-api`):

```
collected 4 items
tests/test_stream_integration.py::test_lavfi_lifecycle PASSED
tests/test_stream_integration.py::test_stream_test_endpoint PASSED
tests/test_stream_integration.py::test_unauthenticated_media_rejected PASSED
tests/test_stream_integration.py::test_report_dir_writable PASSED
=========== 4 passed in 7.59s ===========
```

`test_lavfi_lifecycle` covers, in one pass: admin login → `/streams/config` capabilities (ffmpeg available) → idempotent stop → **start** (state `running`) → poll health until **live frames** (`fps > 0`) → signed `/media` URLs → **HLS chain** (signed master → variant → newest `.ts` segment, `>100 KB`) → **snapshot** (JPEG magic bytes) → **record start/stop** (recording appears in `/recordings`) → **stop** (health `running=false`).

Observed runtime telemetry (via fragment of the lifecycle above):

```
state=running fps=9..26 live=True hls_latency_ms≈2.5
recording: /media/recordings/<cam>/<cam>-20260831T063957Z-935352dc.mp4
finalized:  size_bytes=3928629  duration_seconds=13.68
```

## 4. Fixes / corrections made during validation

1. **mediamtx cookie handshake (kept — was the real blocker).**
   mediamtx redirects the first HLS fetch to `?cookieCheck=1` and sets an `HttpOnly` cookie; a stateless proxy loses the HLS session on that redirect. Fix: one-time handshake in `_mediamtx_hls_cookie()`, replay the `cookieCheck=1` header on every proxied HLS fetch. Verified in-container that master → variant → segment all return `200` with the cookie.

2. **HLS session pinning (removed — impossible by design).**
   Instrumentation proved mediamtx **mints a fresh `session=<uuid>` on every master fetch** and never honors a pinned session token on `index.m3u8` (3 consecutive fetches returned 3 distinct tokens). The session-pinning dict/rewrite logic was dead weight and was reverted; the cookie fix alone makes the chain deterministic. The segment-level 404s previously attributed to session rotation were actually the sliding-window eviction below.

3. **HLS window widened (`hlsSegmentCount: 7 → 15`).**
   mediamtx lists the current window in the media playlist, then evicts the oldest `.ts` as new segments are appended; the oldest listed segment can therefore 404 shortly after the playlist is served (`first` segment 404/200, `last` — the live edge — always 200). Real players (hls.js/Safari) target the live edge, never the evicted tail, so this is non-blocking; a deeper `hlsSegmentCount` additionally decouples it. Sessions idle out (`closed: inactive`) after ~30 s with no requests, which is expected.

4. **Frontend wiring.** Live Wall page lives at `/live` (grouped layout root is `/app`); the sidebar `Live Wall` nav item pointed at `/app/live` and was corrected to `/live`. Web `lint` + `typecheck` clean; `hls.js@1.7.1` installed on the web workspace.

## 5. Browser-equivalent media validation (evidence)

HLS chain **through the Next proxy** (signed media URL from `/media`, resolved same-origin as hls.js does):

```
master    GET /api/v1/streams/<id>/hls/index.m3u8?<sig>      → 200  (rewritten, session + sig embedded)
variant   GET .../hls/main_stream.m3u8?session=...&<sig>      → 200  (#EXTINF playlist)
segment   GET .../hls/<ts>.ts?session=...&<sig>               → 200  (742 KB)
snapshot  GET .../snapshot?<sig>                              → 200  (62 KB JPEG)
```

HLS chain **directly against mediamtx** × 5 iterations (cookie armed): `MASTER 200 / VAR 200 / edge 200 (730 KB) / first 200` every iteration.

Auth model: media endpoints accept **either** a valid `Authorization: Bearer` token **or** a short-lived signed `exp`/`t` query (HMAC). Both paths verified; a no-credentials + bogus-signature request is rejected (401/403).

## 6. Known behaviors / notes for ops

- `POSTGRES_PORT=5433` must be exported before `docker compose` commands on this host.
- Access tokens expire (~30 min); the Live Wall refetches via React Query and re-fetches fresh signed media URLs, so long-running walls stay healthy.
- `.dockerignore` excludes `tests/` from the API image (lean prod build); integration tests are copied in at validation time (`docker cp`) — pytest deps (`pytest`, `pytest-asyncio`) ship in `requirements.txt`.
- Raw `/media` payloads carry the container-internal host (`http://api:8000/...`); the frontend must map them same-origin via `asMediaPath()` (implemented in `apps/web/lib/utils.ts`), which is why the wall feeds hls.js relative paths through the proxy.