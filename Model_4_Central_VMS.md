# Gujarat State CCTV Integration Project
## Model 4: Central VMS (Full Integration)

---

## Document Control

| Parameter | Details |
|-----------|---------|
| Document Title | Model 4 - Central VMS (Full Integration) |
| Version | 1.0 |
| Date | September 2026 |
| Classification | Confidential |
| Model Type | Full Centralized VMS + Analytics + Database Integration |

---

## 1. Executive Summary

Model 4 proposes a **Single Consolidated Central VMS** for integration of CCTV cameras across various departments onto one unified platform. The Central VMS shall enable centralised monitoring, management, recording, storage, playback, and advanced analytics through a common system interface.

**Key Value Proposition:**
- Centralized feed ingestion from all departments
- Tiered storage (Hot, Warm, Cold)
- Advanced AI analytics (ANPR, Face Recognition, Crowd Analysis)
- Statewide vehicle tracking and route reconstruction
- Database integration (VAHAN, SARTHI, eGujCop, AFIS, NAFIS)
- Complete redundancy and disaster recovery

---

## 2. Introduction & Background

### 2.1 Current State

| Department | Camera Count | Storage | Retention | Analytics |
|------------|--------------|---------|-----------|-----------|
| Home Department | 3,500 | Mixed | 7-15 days | Limited |
| RTO | 2,000 | Local | 7 days | Basic ANPR |
| Food & Civil Supplies | 1,500 | Local | 7 days | None |
| Urban Development | 1,200 | Cloud | 15 days | Limited |
| Revenue | 800 | Local | 7 days | None |
| Health | 600 | Local | 7 days | None |
| Others | 3,400 | Mixed | 7-15 days | Limited |
| **Total** | **13,000** | **Fragmented** | **Inconsistent** | **Limited** |

### 2.2 Problem Statement

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT PROBLEMS                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. FRAGMENTED STORAGE                                                       │
│     - No centralized video storage                                          │
│     - Inconsistent retention periods                                        │
│     - No redundancy/backup                                                  │
│                                                                              │
│  2. LIMITED ANALYTICS                                                        │
│     - No unified AI/ML processing                                           │
│     - No cross-department analytics                                         │
│     - No real-time threat detection                                         │
│                                                                              │
│  3. NO DATABASE INTEGRATION                                                  │
│     - Cannot link with VAHAN, SARTHI                                        │
│     - Cannot match with eGujCop, AFIS                                      │
│     - No automated alerts                                                   │
│                                                                              │
│  4. NO STATEWIDE TRACKING                                                    │
│     - Cannot track vehicles across state                                   │
│     - No route reconstruction                                              │
│     - No movement patterns                                                 │
│                                                                              │
│  5. SCALABILITY ISSUES                                                       │
│     - Cannot support 80,000+ cameras                                       │
│     - No horizontal scaling                                                │
│     - No edge processing                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Solution Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 4 SOLUTION OVERVIEW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OBJECTIVE: Fully integrated statewide platform                             │
│                                                                              │
│  APPROACH:                                                                   │
│  ├── Centralized feed ingestion from all sources                           │
│  ├── Tiered storage (Hot/Warm/Cold)                                        │
│  ├── GPU-based AI analytics                                                │
│  ├── Database integration (VAHAN, SARTHI, eGujCop, AFIS, NAFIS)           │
│  ├── Statewide vehicle tracking                                            │
│  └── Complete redundancy and security                                      │
│                                                                              │
│  SCOPE:                                                                      │
│  ✓ Centralized recording and storage                                       │
│  ✓ Advanced AI analytics                                                   │
│  ✓ Database integration                                                    │
│  ✓ Vehicle tracking and route reconstruction                               │
│  ✓ Disaster recovery                                                       │
│  ✓ Full security architecture                                              │
│                                                                              │
│  SCALE:                                                                      │
│  - 80,000+ cameras supported                                               │
│  - 50+ PB storage                                                          │
│  - 1,000+ concurrent analytics                                             │
│  - 10,000+ concurrent users                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Centralized Feed Ingestion

#### 3.1.1 Ingestion Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CENTRALIZED INGESTION ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STATEWIDE CCTV SOURCES                                              │   │
│  │  - Government cameras (13,000)                                      │   │
│  │  - Private entity cameras (5,000+)                                  │   │
│  │  - Future expansion (80,000+)                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  EDGE PROCESSING NODES (33 Districts)                               │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - Local stream processing                                   │   │   │
│  │  │  - Pre-analytics (motion detection, basic ANPR)             │   │   │
│  │  │  - Local caching (7 days hot storage)                       │   │   │
│  │  │  - Bandwidth optimization                                   │   │   │
│  │  │  - Offline operation capability                             │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CENTRAL INGESTION LAYER                                             │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - Stream gateway (10,000+ concurrent streams)              │   │   │
│  │  │  - Protocol normalization (ONVIF, RTSP, SDK)               │   │   │
│  │  │  - Load balancing                                           │   │   │
│  │  │  - Stream quality monitoring                                │   │   │
│  │  │  - Failover management                                     │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CENTRAL VMS PLATFORM                                                │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Recording   │  │  Playback    │  │  Analytics   │              │   │
│  │  │  Engine      │  │  Engine      │  │  Engine      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.1.2 Ingestion Specifications

| Parameter | Specification |
|-----------|---------------|
| Concurrent Streams | 10,000+ |
| Stream Resolution | Up to 4K |
| Frame Rate | 25/30 fps |
| Bitrate | Up to 8 Mbps per stream |
| Protocol Support | ONVIF, RTSP, RTMP, GB/T 28181, SDK |
| Transcoding | H.264, H.265, VP9 |
| Latency | < 2 seconds (live) |

### 3.2 Tiered Storage

#### 3.2.1 Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIERED STORAGE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    HOT STORAGE (NVMe SSD)                           │   │
│  │                                                                      │   │
│  │  - Recent 7 days footage                                           │   │
│  │  - Real-time analytics data                                        │   │
│  │  - Critical alerts                                                 │   │
│  │  - Active metadata                                                 │   │
│  │                                                                      │   │
│  │  Capacity: 100 TB                                                   │   │
│  │  Performance: < 1ms latency                                         │   │
│  │  Cost: ₹800/GB                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    WARM STORAGE (SAS HDD)                          │   │
│  │                                                                      │   │
│  │  - 8-30 days footage                                               │   │
│  │  - Historical analytics                                            │   │
│  │  - Archived metadata                                               │   │
│  │  - Backup data                                                     │   │
│  │                                                                      │   │
│  │  Capacity: 500 TB                                                  │   │
│  │  Performance: < 5ms latency                                         │   │
│  │  Cost: ₹80/GB                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    COLD STORAGE (Object Storage)                    │   │
│  │                                                                      │   │
│  │  - 30+ days footage (up to 1 year)                                 │   │
│  │  - Compliance archives                                             │   │
│  │  - Disaster recovery backups                                       │   │
│  │  - Long-term analytics                                             │   │
│  │                                                                      │   │
│  │  Capacity: 50 PB                                                   │   │
│  │  Performance: < 50ms latency                                        │   │
│  │  Cost: ₹8/GB                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.2.2 Storage Capacity Planning

| Metric | Calculation | Value |
|--------|-------------|-------|
| Total Cameras | Phase 1-4 | 13,000 |
| Future Expansion | Year 5 target | 80,000 |
| Average Resolution | 1080p | 4 Mbps |
| Daily Storage per Camera | 4 Mbps × 86400 sec ÷ 8 | 43.2 GB/day |
| Total Daily Storage (Current) | 13,000 × 43.2 GB | 561.6 TB/day |
| Total Daily Storage (Future) | 80,000 × 43.2 GB | 3.46 PB/day |
| 30-Day Storage (Current) | 561.6 TB × 30 | 16.8 PB |
| With H.265 Compression | 16.8 PB ÷ 3 | 5.6 PB |

### 3.3 AI Analytics Engine

#### 3.3.1 Analytics Capabilities

| Analytics Type | Description | Accuracy Target |
|----------------|-------------|-----------------|
| **ANPR** | Automatic Number Plate Recognition | 98%+ |
| **Face Recognition** | Identify persons from database | 95%+ |
| **Vehicle Recognition** | Make, model, color identification | 90%+ |
| **Crowd Analysis** | Density estimation, counting | 90%+ |
| **Object Detection** | Suspicious objects, abandoned items | 92%+ |
| **Behavior Analysis** | Anomaly detection, loitering | 85%+ |
| **Intrusion Detection** | Zone-based detection | 95%+ |
| **Line Crossing** | Virtual tripwire detection | 95%+ |

#### 3.3.2 Analytics Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AI ANALYTICS ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  GPU INFRASTRUCTURE                                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - NVIDIA A100 GPUs (8 per analytics server)               │   │   │
│  │  │  - TensorRT optimization                                    │   │   │
│  │  │  - Model serving (NVIDIA Triton)                           │   │   │
│  │  │  - Batch processing capability                              │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ANALYTICS PIPELINE                                                  │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Frame       │  │  Pre-process │  │  Inference   │              │   │
│  │  │  Capture     │  │  & Enhance   │  │  Engine      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Post-process│  │  Alert       │  │  Metadata    │              │   │
│  │  │  & Filter    │  │  Generation  │  │  Storage     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  AI MODELS                                                          │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  ANPR Model  │  │  Face Model  │  │  Vehicle     │              │   │
│  │  │  (YOLOv8 +   │  │  (InsightFace│  │  Model       │              │   │
│  │  │   CRNN)      │  │   + ArcFace) │  │  (YOLOv8)    │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Crowd Model │  │  Object      │  │  Behavior    │              │   │
│  │  │  (CSRNet)    │  │  Detection   │  │  Analysis    │              │   │
│  │  │              │  │  (YOLOv8)    │  │  (LSTM)      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.3 ANPR Engine

| Feature | Specification |
|---------|---------------|
| Detection Model | YOLOv8 |
| Recognition Model | CRNN + CTC |
| Indian Plate Formats | All states supported |
| Processing Speed | < 0.5 second per plate |
| Accuracy | 98%+ (good conditions) |
| Multi-plate Detection | Up to 10 plates per frame |
| Night Support | IR-enhanced processing |

#### 3.3.4 Face Recognition Engine

| Feature | Specification |
|---------|---------------|
| Detection Model | RetinaFace |
| Recognition Model | ArcFace |
| Database Size | 100,000+ faces |
| Processing Speed | < 1 second per face |
| Accuracy | 95%+ (Top-1) |
| Anti-spoofing | Liveness detection |
| Mask Support | Mask-tolerant recognition |

### 3.4 Database Integration

#### 3.4.1 VAHAN Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VAHAN INTEGRATION                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DATA FLOW                                                           │   │
│  │                                                                      │   │
│  │  CCTV System ──▶ API Gateway ──▶ VAHAN API ──▶ Response             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DATA MAPPING                                                        │   │
│  │                                                                      │   │
│  │  CCTV Data            VAHAN Data                                    │   │
│  │  ─────────            ──────────                                    │   │
│  │  License Plate   ──▶  Vehicle Number                                │   │
│  │  Timestamp       ──▶  Registration Date                             │   │
│  │  Location        ──▶  Registered RTO                                │   │
│  │  Vehicle Type    ──▶  Vehicle Class                                 │   │
│  │  Color           ──▶  Vehicle Color                                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ALERT TRIGGERS                                                      │   │
│  │                                                                      │   │
│  │  - Stolen Vehicle Detected                                          │   │
│  │  - Invalid Registration                                             │   │
│  │  - Expired Insurance                                                │   │
│  │  - Blacklisted Vehicle                                              │   │
│  │  - Tax Default                                                      │   │
│  │  - Fitness Certificate Expired                                      │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.4.2 SARTHI Integration

| Feature | Description |
|---------|-------------|
| Challan Lookup | Get challan details by plate |
| Violation History | Driver violation history |
| Fine Status | Pending fine status |
| License Status | License validity check |
| Alert Triggers | Repeat violators, suspended licenses |

#### 3.4.3 eGujCop Integration

| Feature | Description |
|---------|-------------|
| Criminal Database | Match face with criminal records |
| FIR Database | Link incidents with FIRs |
| Missing Persons | Identify missing persons |
| Stolen Property | Link with stolen property cases |
| Alert Triggers | Wanted persons, accused persons |

#### 3.4.4 AFIS/NAFIS Integration

| Feature | Description |
|---------|-------------|
| Fingerprint Match | 1:N fingerprint identification |
| Template Storage | Secure template storage |
| Match Confidence | Confidence score |
| Integration Type | API-based, on-demand |
| Response Time | < 5 seconds |

### 3.5 Statewide Vehicle Tracking

#### 3.5.1 Tracking Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Real-time Tracking | Track vehicle movement | Mandatory |
| Route Reconstruction | Reconstruct vehicle route | Mandatory |
| Movement Patterns | Analyze movement patterns | Mandatory |
| Geofencing | Alert when vehicle enters zone | Mandatory |
| Historical Playback | Playback vehicle history | Mandatory |
| Export | Export tracking data | Mandatory |

#### 3.5.2 Vehicle Tracking Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VEHICLE TRACKING WORKFLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Plate     │───▶│   Database  │───▶│   Route     │───▶│   Alert     │ │
│  │   Detected  │    │   Lookup    │    │   Update    │    │   Check     │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TRACKING DATA STRUCTURE                                             │   │
│  │                                                                      │   │
│  │  {                                                                   │   │
│  │    "plate_number": "GJ01AB1234",                                   │   │
│  │    " sightings": [                                                  │   │
│  │      { "timestamp": "...", "camera": "...", "location": {...} },   │   │
│  │      { "timestamp": "...", "camera": "...", "location": {...} },   │   │
│  │      ...                                                             │   │
│  │    ],                                                                │   │
│  │    "route": {                                                        │   │
│  │      "type": "LineString",                                          │   │
│  │      "coordinates": [[lon, lat], ...]                               │   │
│  │    },                                                                │   │
│  │    "total_distance_km": 45.5,                                       │   │
│  │    "total_time_hours": 2.5,                                         │   │
│  │    "average_speed_kmh": 18.2                                        │   │
│  │  }                                                                   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technical Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 4 SYSTEM ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STATEWIDE CCTV SOURCES                                              │   │
│  │  Government + Private + Future cameras                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  EDGE LAYER (33 District Nodes)                                     │   │
│  │  - Local processing    - Hot storage (7 days)                      │   │
│  │  - Pre-analytics       - Bandwidth optimization                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CENTRAL DATA CENTER                                                  │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  INGESTION LAYER                                              │   │   │
│  │  │  - Stream Gateway (10,000+ streams)                          │   │   │
│  │  │  - Protocol Adapters                                          │   │   │
│  │  │  - Load Balancers                                             │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  PROCESSING LAYER                                            │   │   │
│  │  │  - Recording Engine                                          │   │   │
│  │  │  - Transcoding Engine                                        │   │   │
│  │  │  - Analytics Engine (GPU)                                    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  STORAGE LAYER                                               │   │   │
│  │  │  - Hot Storage (NVMe SSD) - 100 TB                          │   │   │
│  │  │  - Warm Storage (SAS HDD) - 500 TB                          │   │   │
│  │  │  - Cold Storage (Object) - 50 PB                            │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  APPLICATION LAYER                                           │   │   │
│  │  │  - VMS Core (Recording, Playback, Export)                   │   │   │
│  │  │  - Analytics Services (ANPR, Face, Vehicle)                 │   │   │
│  │  │  - Database Services (VAHAN, SARTHI, eGujCop, AFIS)        │   │   │
│  │  │  - Tracking Services (Vehicle, Route)                       │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  USER LAYER                                                          │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Command     │  │  Web         │  │  Mobile      │              │   │
│  │  │  Center UI   │  │  Dashboard   │  │  App         │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Database Schema

```sql
-- Core Tables
CREATE TABLE cameras (
    id UUID PRIMARY KEY,
    camera_id VARCHAR(50) UNIQUE NOT NULL,
    department_id UUID REFERENCES departments(id),
    location_name VARCHAR(200),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    geom GEOMETRY(Point, 4326),
    camera_make VARCHAR(100),
    camera_model VARCHAR(100),
    camera_type VARCHAR(20),
    resolution VARCHAR(20),
    protocol VARCHAR(20),
    storage_tier VARCHAR(20),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Recording Metadata
CREATE TABLE recordings (
    id UUID PRIMARY KEY,
    camera_id UUID REFERENCES cameras(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    file_path VARCHAR(500),
    file_size BIGINT,
    storage_tier VARCHAR(20),
    retention_days INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analytics Events
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY,
    camera_id UUID REFERENCES cameras(id),
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    confidence DECIMAL(5, 4),
    metadata JSONB,
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ANPR Records
CREATE TABLE anpr_records (
    id UUID PRIMARY KEY,
    camera_id UUID REFERENCES cameras(id),
    plate_number VARCHAR(20) NOT NULL,
    confidence DECIMAL(5, 4),
    timestamp TIMESTAMP NOT NULL,
    vehicle_make VARCHAR(100),
    vehicle_model VARCHAR(100),
    vehicle_color VARCHAR(50),
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Face Records
CREATE TABLE face_records (
    id UUID PRIMARY KEY,
    camera_id UUID REFERENCES cameras(id),
    person_id UUID,
    confidence DECIMAL(5, 4),
    timestamp TIMESTAMP NOT NULL,
    image_url VARCHAR(500),
    embedding VECTOR(512),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vehicle Tracking
CREATE TABLE vehicle_tracking (
    id UUID PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    camera_id UUID REFERENCES cameras(id),
    timestamp TIMESTAMP NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    geom GEOMETRY(Point, 4326),
    speed DECIMAL(5, 2),
    direction DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    source_id UUID,
    source_type VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    title VARCHAR(200),
    description TEXT,
    status VARCHAR(20) DEFAULT 'new',
    assigned_to UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Database Integration Logs
CREATE TABLE db_integration_logs (
    id UUID PRIMARY KEY,
    database_name VARCHAR(50) NOT NULL,
    query_type VARCHAR(20),
    query_params JSONB,
    response_data JSONB,
    response_time_ms INTEGER,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Spatial Indexes
CREATE INDEX idx_cameras_geom ON cameras USING GIST(geom);
CREATE INDEX idx_recordings_camera ON recordings(camera_id);
CREATE INDEX idx_recordings_time ON recordings(start_time, end_time);
CREATE INDEX idx_analytics_camera ON analytics_events(camera_id);
CREATE INDEX idx_analytics_time ON analytics_events(timestamp);
CREATE INDEX idx_anpr_plate ON anpr_records(plate_number);
CREATE INDEX idx_anpr_time ON anpr_records(timestamp);
CREATE INDEX idx_tracking_plate ON vehicle_tracking(plate_number);
CREATE INDEX idx_tracking_time ON vehicle_tracking(timestamp);
CREATE INDEX idx_tracking_geom ON vehicle_tracking USING GIST(geom);
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_time ON alerts(timestamp);
```

### 4.3 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **VMS Core** | | | |
| Recording Engine | Custom (Go) | - | Video recording |
| Playback Engine | Custom (Go) | - | Video playback |
| Export Engine | FFmpeg | 6.x | Video export |
| **Analytics** | | | |
| ANPR | YOLOv8 + CRNN | Latest | Plate recognition |
| Face Recognition | InsightFace + ArcFace | Latest | Face recognition |
| Vehicle Recognition | YOLOv8 | Latest | Vehicle detection |
| Crowd Analysis | CSRNet | Latest | Crowd counting |
| Model Serving | NVIDIA Triton | 23.x | GPU inference |
| **Database** | | | |
| Primary | PostgreSQL | 16 | Transactional data |
| Time Series | TimescaleDB | 2.x | Event data |
| Vector | pgvector | 0.5+ | Face embeddings |
| Object Storage | MinIO / Ceph | Latest | Video files |
| Cache | Redis | 7.x | Session cache |
| Search | Elasticsearch | 8.x | Full-text search |
| **Infrastructure** | | | |
| Container | Docker | Latest | Containerization |
| Orchestration | Kubernetes | 1.28+ | Deployment |
| Message Queue | Apache Kafka | 3.x | Event streaming |
| API Gateway | Kong | 3.x | API management |

---

## 5. Security Architecture

### 5.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PERIMETER SECURITY                                                  │   │
│  │  - Web Application Firewall (WAF)                                   │   │
│  │  - DDoS Protection                                                  │   │
│  │  - IP Whitelisting                                                  │   │
│  │  - Rate Limiting                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  NETWORK SECURITY                                                   │   │
│  │  - Network Segmentation (VLAN)                                      │   │
│  │  - Firewall Rules                                                   │   │
│  │  - IDS/IPS                                                          │   │
│  │  - SSL/TLS Encryption                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  APPLICATION SECURITY                                               │   │
│  │  - OAuth 2.0 / JWT Authentication                                   │   │
│  │  - Role-Based Access Control (RBAC)                                 │   │
│  │  - Input Validation                                                 │   │
│  │  - SQL Injection Protection                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DATA SECURITY                                                      │   │
│  │  - Encryption at Rest (AES-256)                                     │   │
│  │  - Encryption in Transit (TLS 1.3)                                  │   │
│  │  - Data Masking                                                     │   │
│  │  - Backup Encryption                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  COMPLIANCE                                                         │   │
│  │  - IT Act 2000                                                      │   │
│  │  - DPDP Act 2023                                                    │   │
│  │  - CERT-In Guidelines                                               │   │
│  │  - Audit Logging                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Disaster Recovery

| Parameter | Target |
|-----------|--------|
| RPO (Recovery Point Objective) | 1 hour |
| RTO (Recovery Time Objective) | 4 hours |
| Availability | 99.95% |
| Backup Frequency | Every 6 hours |
| Backup Retention | 30 days |
| DR Site | Alternate data center |

---

## 6. Scalability Design

### 6.1 Horizontal Scaling

| Component | Scaling Strategy |
|-----------|------------------|
| Stream Ingestion | Add stream gateway nodes |
| Analytics | Add GPU servers |
| Storage | Add storage nodes |
| Database | Read replicas, sharding |
| Application | Kubernetes pod scaling |

### 6.2 Capacity Planning

| Metric | Current | Year 1 | Year 3 | Year 5 |
|--------|---------|--------|--------|--------|
| Cameras | 13,000 | 20,000 | 50,000 | 80,000 |
| Storage | 5.6 PB | 10 PB | 25 PB | 50 PB |
| Analytics | 1,000 | 5,000 | 20,000 | 40,000 |
| Users | 500 | 1,000 | 3,000 | 5,000 |

---

## 7. Deliverables

| # | Deliverable | Description | Acceptance Criteria |
|---|-------------|-------------|---------------------|
| 1 | **Central VMS Prototype** | Working prototype | Multi-department feeds |
| 2 | **ANPR Demonstration** | Live ANPR | 98%+ accuracy |
| 3 | **Vehicle Tracking** | Multi-location tracking | Route reconstruction |
| 4 | **Scalability Report** | Load test for 80K cameras | Report delivered |
| 5 | **DR Design** | Disaster recovery plan | Document approved |
| 6 | **Security Document** | Security architecture | Audit passed |
| 7 | **Database Integration** | VAHAN, SARTHI, eGujCop | Working integration |
| 8 | **API Documentation** | Complete API docs | OpenAPI/Swagger |

---

## 8. Implementation Plan

| Phase | Duration | Activities |
|-------|----------|------------|
| Phase 1 | Month 1-6 | Infrastructure setup |
| Phase 2 | Month 7-12 | Core VMS development |
| Phase 3 | Month 13-18 | Analytics engine |
| Phase 4 | Month 19-24 | Database integration |
| Phase 5 | Month 25-30 | Testing & optimization |
| Phase 6 | Month 31-36 | Full deployment |

---

## 9. Success Metrics

| Metric | Target |
|--------|--------|
| Camera Integration | 80,000+ |
| System Uptime | 99.95% |
| ANPR Accuracy | 98%+ |
| Face Recognition Accuracy | 95%+ |
| Alert Response Time | < 5 seconds |
| Storage Efficiency | 90%+ utilization |

---

*Document Version: 1.0*
*Date: September 2026*
*Model: 4 - Central VMS (Full Integration)*