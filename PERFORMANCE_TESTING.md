# Reproducible performance checks

The repository includes a deterministic HTTP smoke benchmark for the public health endpoint.

```powershell
$env:SENTINEL_LOAD_URL = "http://127.0.0.1:8000/api/v1/health"
$env:SENTINEL_LOAD_SECONDS = "10"
$env:SENTINEL_LOAD_CONNECTIONS = "10"
npm run test:load
```

The command exits non-zero when requests fail, time out, or p99 latency exceeds the default 5000 ms acceptance threshold. Override it with `SENTINEL_LOAD_MAX_P99_MS` when a deployment has a measured service-level objective. The JSON output records the URL, duration, concurrency, threshold, throughput, latency distribution, and error counts. Run it against the same Compose profile and hardware when comparing baselines; no fixed throughput claim is made because host hardware and database state affect the result.

## Recorded local baseline

On 2026-09-06, using 10 seconds and 10 connections against `http://127.0.0.1:8000/api/v1/health`, the run completed with 40 requests, 0 errors, 0 timeouts, approximately 4 requests/second, and 2122 ms p99 latency. This is a reproducibility reference, not a production capacity claim.

## TestClient compatibility note

The backend currently pins `httpx==0.28.1`. The installed Starlette version emits a deprecation warning recommending a future `httpx2` compatibility path. The warning was not suppressed or “fixed” by changing the pin: the complete backend suite has not been verified against that alternate client package in the repository's Docker environment, so changing it would be an unverified dependency migration.
