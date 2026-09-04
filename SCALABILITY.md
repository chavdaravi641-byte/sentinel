# Police Sentinel — Enterprise Scalability Architecture (Roadmap to 80,000 Cameras)

This document describes the production architecture required to scale the
**Police Sentinel** platform from the current MVP (50 feads) to a full-state
deployment of **~80,000 heterogeneous CCTV cameras** while preserving real-time
ANPR latency (<100 ms), cross-referencing against VAHAN/eGujCop/SARTHI watchlists,
and live GIS traversal reconstruction.

---

## 1. Current Architecture (MVP)

The working MVP is a **single-region, hub-and-spoke** topology:

```
50 cameras ──RTSP/HLS──▶ MediaMTX ──▶ HLS/WHEP ──▶ Browser Clients
                     │
                     └──▶ FFmpeg/OpenCV ──▶ YOLO ANPR ──▶ PostGIS/PostgreSQL
                                                  │
                                                  └──▶ Redis Pub/Sub ──▶ WebSocket
```

| Layer | Tech | Scale today |
|-------|------|-------------|
| Ingestion | FFmpeg + OpenCV (server side) | 16 concurrent streams |
| Media relay | MediaMTX (go2rtc-grade) | 16 WHEP/HLS fan-out |
| AI | YOLOv12 ONNX, sim backend | Per-camera 5 FPS |
| Event store | PostgreSQL + PostGIS | ~10k rows/day |
| Bus | Redis Pub/Sub | Single node |

**Bottlenecks at 80k cameras:** central transcoding, single Postgres writer,
single-node Redis, full-video WAN transport, and one logical LAN.

---

## 2. Edge Inference Layer (the single biggest win)

**Principle: never ship full video over WAN.** Move ANPR + object detection to
edge nodes collocated with or near the camera.

```
   Camera ──RTSP(local)──▶ Edge Device (Jetson Orin / Edge NVR)
                              │  1. YOLO ANPR at 15–30 FPS on 1080p
                              │  2. Vehicle attribute fusion (color/make)
                              │  3. Emit ~300-byte metadata JSON
                              ▼
                        Kafka topic: anpr.detections
                              │  partition key = district_id
                              ▼
                   Central Dir Com ms: alert engine + GIS + watchlist match
```

**Edge hardware options:**

| Device | ANPR FPS | Cameras/device | Notes |
|--------|----------|----------------|-------|
| Jetson Orin Nano | 30 | 4–8 | ~15W, ideal for district clusters |
| Jetson AGX Orin | 60 | 16–32 | Heavier attribute models |
| Edge NVR (e.g. Hikvision NVR 8ch) | 15 | 8 | No GPU; CPU YOLO tiny |
| CPU-only micro (RPi5/Intel N100) | 5–10 | 1–2 | Cheapest, lowest tier |

**What travels on the WAN (≈0.4 GB/day/device):**
- ANPR metadata JSON (`{plate, conf, vehicle_attrs, camera, ts}`)
- 4–8 evidence JPGs per alarm (only when a hot watchlist plate matches)
- Low-bitrate 480p sub-stream for the Command Center video wall (on demand)

**Safety net:** if an edge node dies, fall back to a neighbour edge node
(raft-managed ownership — already prototyped in `src/cluster`).

---

## 3. Message Bus — Apache Kafka

Replace Redis Pub/Sub with **Apache Kafka** for the event backbone.

```
Topics:
  anpr.detections       → partition key: district_id (guarantees per-district ordering)
  anpr.alerts.hot       → compaction enabled (latest state per plate)
  media.telemetry       → edge → VMS heartbeat, FPS, GPU util
  cams.status           → camera online/offline transitions
  gis.feed              → camera node geometry for the map
```

**Throughput math (80k cameras, 5 FPS detection):**

| Metric | Value |
|--------|-------|
| Detections/sec | 80,000 × 5 = **400k events/s** peak |
| Event size | ~300 bytes → **~120 MB/s** sustained |
| Kafka partitions | 33 districts → safe, ordered distribution |
| Redundancy | replication.factor=3, min.insync=2 |

**Kafka sizing:** 3 brokers × (NVMe, 32-core) can absorb 400k/s with acks=1.
Use KRaft mode (no ZooKeeper). Retain detections 90 days in compacted topics;
cold segments age to S3 via Kafka Connect.

---

## 4. Distributed Storage — Tiered Architecture

```
Tier 0  HOT  (0–6 h)   Redis / TimescaleDB (in-memory / high-write) ── analytics + live alerts
Tier 1  WARM (6 h–15 d) PostgreSQL + PostGIS, partitioned by district+day ── GIS + case work
Tier 2  COLD (15 d–2 y) S3 / Ceph object store ── raw video + evidence JPGs
```

**Video retention (~2 TB/day across 80k cameras at 15-day warm window):**

| Tier | Storage | Size | Cost/leaf |
|------|---------|------|-----------|
| Hot events | NVMe Redis | ~1 TB | high I/O |
| PostGIS | NVMe/SSD ×6 | ~20 TB | partitioned |
| Video (15 d) | Ceph erasure-coded | ~30 TB ×2 copies | cheapest |

**Postgres partitioning:**
```
PARTITION BY RANGE (ts)  +  SUBPARTITION BY HASH (district_id)
```
Queries like "all sightings of plate GJ01AB1234 today" become a `WHERE
district_id IN (...)` scan over a single day partition — sub-second even at
multi-million-row volumes.

**PostGIS:** geometry columns on `camera_registry` (`geom`, GIST index) power
nearest-neighbour, within-buffer, and coverage-union queries. The MVP keeps pure
Python geometry (no extension required) — see `src/registry/gis_sql.py` for the
ready-to-run production SQL.

---

## 5. Orchestration — Kubernetes

Helm charts describe the control plane:

```
charts/
  sentinel-api/          FastAPI stateless pods (HPA on CPU / RPS)
  sentinel-worker/       ANPR consumers (HPA on Kafka lag → message-rate)
  sentinel-edge/         Edge agent daemonset (per site)
  sentinel-gis/          Map/WebSocket fan-out servers (HPA on WS conns)
  sentinel-mythmedia/    MediaMTX relay replicas (rebind per shard)
  sentinel-kafka/        Krakend/Strimzi Kafka operator
  sentinel-postgis/      CloudNativePG operator, PgBouncer pooler
  sentinel-redis/        Redis Cluster (3 pods, 6 shards)
  sentinel-s3/           MinIO / Ceph RGW object store
```

**Autoscaling policy:**

| Metric | Trigger | Action |
|--------|---------|--------|
| Kafka consumer lag | > 10k msg | +2 ANPR worker pods |
| WS connections | > 5k / pod | +1 GIS pod |
| API RPS | > 200 / pod | +1 API pod |
| GPU saturation | > 85% on edge | offload to neighbour node |

Multi-AZ spread, pod anti-affinity, PDBs, and a two-pool node group
(general vs. GPU).

---

## 6. Command Center Data Plane

For ≤2,000 officer clients, keep Redis Pub/Sub as the **realtime fan-out** for
WebSockets (per-connection pub/sub + a tiny in-process channel cache), while
Kafka holds the authoritative event log. At >2,000 concurrent clients, shard
WS servers per district and use Redis Cluster.

**Alert latency budget (<100 ms):**
```
edge ANPR  → Kafka  →  alert engine (10 ms)  →  Redis  →  WS  →  client
   5 ms           10 ms              5 ms             10 ms         ~50 ms
```

---

## 7. Watchlist Cross-Referencing at Scale

- **Hot watchlist** (≤10k plates) — a Redis hash + in-memory trie on every
  consumer/edge node for O(1) plate match.
- **Cold/legacy watchlist** (VAHAN/eGujCop full DUMP, millions of rows) —
  PostgreSQL BRIN/GIN on `identifier_number`; background sync into the hot cache
  every 60 s (configurable, already prototyped via
  `ANPR_BLACKLIST_SYNC_SECONDS=60`).
- **Matching engine** runs server-side on every `anpr.detections` event before
  any alert is emitted; matching bucketised by 2-letter district prefix, then
  exact plate.

---

## 8. Cost & Capacity Estimates (80k cameras)

| Resource | Unit est. |
|----------|-----------|
| Edge devices | 80k × 6 cameras → **~13.5k Jetson/NVR units** |
| Kafka brokers | 3 × 32-core / 128 GB / 4×NVMe 1.9 TB |
| PostGIS (warm) | 6 × 32-core / 512 GB / 6×NVMe 3.8 TB |
| Redis (hot) | 6 × 16-core / 64 GB |
| Object store | Ceph 3 × 12 OSD × 16 TB |
| API / GIS / WS | ~30 × 16-core pods (HPA) |
| WAN video | only sub-stream + alarm JPGs (~0.4 GB/day/device) |

---

## 9. Migration Path from MVP

1. **Single-region → multi-district** — introduce `district_id` on cameras;
   partition tables; publish registry to PostGIS geometry columns.
2. **Hub ANPR → edge ANPR** — ship the ONNX weights to Jetsons; run each device
   as a self-contained ANPR worker; keep server sim backend as fallback.
3. **Redis-only bus → Kafka** — dual-write during transition; cut over consumers
   to Kafka, flip Redis to WS fan-out only.
4. **Postgres single → partitioned + PgBouncer** — add PgBouncer, add day/district
   partitions, move insert load to workers.
5. **Container → K8s** — package as Helm charts; enable HPA; adopt operators.

---

## 10. Assumptions & Open Decisions

- **Video transport:** default to H.264 sub-stream; H.265/AV1 where edge GPU
  supports it.
- **Alert prioritisation:** stagger severity so alarms never exceed operator
  throughput (critical ≤ 1% of events).
- **WAN QoS:** dedicated policy to guarantee <50 ms between edge and central
  Kafka for real-time alerts.
- **Geofencing:** PostGIS ST_DWithin on camera geometry for district boundaries
  (camera ownership = district of the geometry they sit in).

This roadmap is deliberately incremental — every milestone is independently
shippable and the MVP already contains the device-ownership, geometry-SQL, and
branch-and-partition primitives needed for the first step.