# Gujarat State CCTV Integration Project
## Detailed Technical Design Document

---

## Document Information

| Parameter | Details |
|-----------|---------|
| Document Title | Detailed Technical Design |
| Version | 1.0 |
| Date | September 2026 |
| Classification | Confidential |
| Prepared For | Gujarat State Government |

---

## 1. Executive Summary

This document provides the detailed technical design for the Gujarat State CCTV Integration Project. The system will integrate 26 government department CCTV networks into a unified platform with advanced analytics and database integration capabilities.

---

## 2. System Architecture

### 2.1 High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Web Portal  │  │ Mobile App   │  │  Command     │  │   Public     │   │
│  │              │  │              │  │  Center UI   │  │   Display    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY LAYER                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     API Gateway (Kong/AWS API Gateway)               │  │
│  │  - Authentication  - Rate Limiting  - Load Balancing  - Logging     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          APPLICATION LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Video       │  │  Analytics   │  │  Database    │  │  Alert       │   │
│  │  Management   │  │   Engine     │  │ Integration  │  │  Service     │   │
│  │   Service     │  │              │  │   Service    │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INTEGRATION LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Protocol    │  │   Camera     │  │   Storage    │  │   Network    │   │
│  │   Gateway     │  │  Connectors  │  │   Connectors │  │  Connectors  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Video       │  │   Metadata   │  │   Analytics  │  │   Audit      │   │
│  │   Storage     │  │   Database   │  │   Database   │  │   Logs       │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXISTING INFRASTRUCTURE LAYER                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │ Home    │ │ Food &  │ │  RTO    │ │ Health  │ │ Education│ │  Other  │ │
│  │ Dept    │ │ Civil   │ │         │ │ Dept    │ │  Dept    │ │ 23 Depts│ │
│  │         │ │ Supplies│ │         │ │         │ │         │ │         │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Architecture

#### 2.2.1 Video Management System (VMS)

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIDEO MANAGEMENT SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Core VMS Engine                         │   │
│  │  - Stream Management    - Recording Management          │   │
│  │  - Playback Engine      - Export Engine                  │   │
│  │  - Health Monitoring    - Failover Management            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Camera Abstraction Layer                    │   │
│  │  - Protocol Adapters    - Device Drivers                 │   │
│  │  - Format Converters    - Stream Normalizers             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Storage Management Layer                    │   │
│  │  - Cloud Storage        - Local Storage                  │   │
│  │  - Hybrid Storage       - Retention Policies             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**

| Component | Description | Technology |
|-----------|-------------|------------|
| Stream Manager | Manages live video streams | GStreamer/FFmpeg |
| Recording Manager | Handles video recording & storage | Custom + MinIO |
| Playback Engine | Historical video retrieval | Custom |
| Health Monitor | Camera/system health tracking | Prometheus + Grafana |
| Failover Manager | Automatic failover handling | Custom |

#### 2.2.2 Analytics Engine

```
┌─────────────────────────────────────────────────────────────────┐
│                      ANALYTICS ENGINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Video Analytics Modules                  │   │
│  │  - Face Recognition      - Vehicle Recognition          │   │
│  │  - Object Detection      - Behavior Analysis            │   │
│  │  - Crowd Analysis        - Intrusion Detection          │   │
│  │  - License Plate Recognition  - abandoned Object        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 AI/ML Processing Layer                   │   │
│  │  - Model Serving (TensorRT/ONNX)                        │   │
│  │  - GPU Resource Management                              │   │
│  │  - Model Versioning & Updates                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Event Processing Layer                   │   │
│  │  - Event Queue (Kafka)    - Alert Generator             │   │
│  │  - Correlation Engine     - Notification Service         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Analytics Capabilities:**

| Analytics Type | Use Case | Database Link |
|----------------|----------|---------------|
| Face Recognition | Criminal identification | eGujCop, AFIS, NAFIS |
| Vehicle Recognition | Stolen vehicle detection | VAHAN, SARTHI |
| License Plate Recognition | Traffic violation | SARTHI |
| Crowd Analysis | Law & order monitoring | - |
| Intrusion Detection | Border security | - |
| Behavior Analysis | Suspicious activity | - |

#### 2.2.3 Database Integration Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                 DATABASE INTEGRATION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Database Connectors                         │   │
│  │                                                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │   │
│  │  │ VAHAN   │ │ SARTHI  │ │ eGujCop │ │ AFIS/   │      │   │
│  │  │Connector│ │Connector│ │Connector│ │NAFIS    │      │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Data Synchronization                        │   │
│  │  - Real-time Sync        - Batch Sync                    │   │
│  │  - Conflict Resolution   - Data Validation               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Query Optimization                          │   │
│  │  - Caching Layer         - Query Routing                 │   │
│  │  - Index Management      - Performance Monitoring        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Database Integration Details:**

| Database | Integration Type | Data Flow | Frequency |
|----------|------------------|-----------|-----------|
| VAHAN | API-based | Bidirectional | Real-time |
| SARTHI | API-based | Bidirectional | Real-time |
| eGujCop | API-based | Read-heavy | Real-time |
| AFIS | API-based | Read-heavy | On-demand |
| NAFIS | API-based | Read-heavy | On-demand |

---

## 3. Infrastructure Design

### 3.1 Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STATE-LEVEL DATA CENTER                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Core Network                                  │   │
│  │  - 100 Gbps Backbone     - Redundant Links                          │   │
│  │  - MPLS/SD-WAN           - VPN Connectivity                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Security Zone                                 │   │
│  │  - Firewall ( Palo Alto / Fortinet )                                │   │
│  │  - IDS/IPS              - DDoS Protection                           │   │
│  │  - SSL VPN              - Network Segmentation                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DISTRICT-LEVEL NODES                                    │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Ahmedabad  │  │  Surat      │  │  Vadodara   │  │  Rajkot     │       │
│  │   Node      │  │   Node      │  │   Node      │  │   Node      │       │
│  │  - Edge     │  │  - Edge     │  │  - Edge     │  │  - Edge     │       │
│  │  - Local    │  │  - Local    │  │  - Local    │  │  - Local    │       │
│  │  - Storage  │  │  - Storage  │  │  - Storage  │  │  - Storage  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Valsad     │  │  Dahod      │  │  Somnath    │  │  Jamnagar   │       │
│  │   Node      │  │   Node      │  │   Node      │  │   Node      │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SITE-LEVEL DEPLOYMENT                                   │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Home      │  │  Food &     │  │    RTO      │  │  Private    │       │
│  │  Department │  │  Civil      │  │  Office     │  │  Entities   │       │
│  │   Sites     │  │  Supplies   │  │   Sites     │  │   Sites     │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Server Infrastructure

#### 3.2.1 State Data Center (Primary)

| Server Role | Specifications | Quantity | Purpose |
|-------------|----------------|----------|---------|
| Application Servers | 64 Cores, 256 GB RAM, 4x 1TB SSD | 4 | Core platform |
| Database Servers | 64 Cores, 512 GB RAM, 8x 2TB NVMe | 4 | Data storage |
| Analytics Servers | 64 Cores, 256 GB RAM, 2x GPU (A100) | 4 | AI/ML processing |
| Storage Servers | 32 Cores, 128 GB RAM, 20x 4TB HDD | 6 | Video storage |
| Network Servers | 32 Cores, 64 GB RAM | 2 | Network management |

#### 3.2.2 District Nodes (33 Districts)

| Server Role | Specifications | Quantity per District | Purpose |
|-------------|----------------|----------------------|---------|
| Edge Servers | 16 Cores, 64 GB RAM, 2x 1TB SSD | 2 | Local processing |
| Storage Nodes | 8 Cores, 32 GB RAM, 10x 4TB HDD | 2 | Local storage |
| Network Equipment | Managed Switch, Router | 1 set | Local networking |

### 3.3 Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STORAGE ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    HOT STORAGE (NVMe SSD)                           │   │
│  │  - Recent 7 days footage     - Real-time analytics data            │   │
│  │  - Critical alerts           - Active metadata                     │   │
│  │  - Capacity: 100 TB          - Performance: < 1ms latency          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    WARM STORAGE (SAS HDD)                          │   │
│  │  - 8-30 days footage         - Historical analytics                 │   │
│  │  - Archived metadata         - Backup data                         │   │
│  │  - Capacity: 500 TB          - Performance: < 5ms latency          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    COLD STORAGE (Object Storage)                    │   │
│  │  - 30+ days footage          - Compliance archives                  │   │
│  │  - Long-term retention       - Disaster recovery                    │   │
│  │  - Capacity: 2 PB            - Performance: < 50ms latency         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Storage Capacity Planning:**

| Metric | Calculation | Value |
|--------|-------------|-------|
| Total Cameras | 26 departments × Avg 500 cameras | 13,000 cameras |
| Resolution | 1080p (4 Mbps avg) | 4 Mbps per camera |
| Daily Storage per Camera | 4 Mbps × 86400 sec ÷ 8 | 43.2 GB/day |
| Total Daily Storage | 13,000 × 43.2 GB | 561.6 TB/day |
| 30-Day Storage | 561.6 TB × 30 | 16.8 PB |
| With Compression (H.265) | 16.8 PB ÷ 3 | 5.6 PB |

### 3.4 Network Design

#### 3.4.1 Bandwidth Requirements

| Connection Type | Bandwidth | Purpose |
|-----------------|-----------|---------|
| State DC to District | 10 Gbps | Primary connectivity |
| District to Sites | 1 Gbps | Camera feed传输 |
| VPN Tunnels | 100 Mbps | Secure communication |
| Internet Gateway | 1 Gbps | External access |

#### 3.4.2 Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATE DATA CENTER                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Core Switch (100G)                     │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │   │
│  │  │ App     │  │ DB      │  │ Storage │  │ Analytics│   │   │
│  │  │ Servers │  │ Servers │  │ Servers │  │ Servers  │   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Distribution Switch (40G)                   │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │   │
│  │  │ Firewall│  │ Router  │  │ Load    │  │ VPN     │   │   │
│  │  │         │  │         │  │ Balancer│  │ Gateway │   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │  MPLS/SD-WAN  │ │  MPLS/SD-WAN  │ │  MPLS/SD-WAN  │
    │    Ahmedabad  │ │    Surat      │ │    Rajkot     │
    └───────────────┘ └───────────────┘ └───────────────┘
            │               │               │
            ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │ District Node │ │ District Node │ │ District Node │
    │   Switch      │ │   Switch      │ │   Switch      │
    └───────────────┘ └───────────────┘ └───────────────┘
            │               │               │
    ┌───────┴───────┐ ┌─────┴─────┐ ┌───────┴───────┐
    │ Site Switches │ │Site Switch│ │ Site Switches │
    └───────────────┘ └───────────┘ └───────────────┘
```

---

## 4. Software Architecture

### 4.1 Technology Stack

#### 4.1.1 Backend Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Programming Language | Java 17 / Go 1.21 | Core services |
| API Framework | Spring Boot / Gin | REST API |
| Message Queue | Apache Kafka | Event streaming |
| Cache | Redis Cluster | Session, caching |
| Search Engine | Elasticsearch | Metadata search |
| Container Orchestration | Kubernetes | Service deployment |
| Service Mesh | Istio | Service communication |

#### 4.1.2 Frontend Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | React 18 / Angular 17 | Web dashboard |
| Mobile Framework | React Native / Flutter | Mobile app |
| UI Library | Material UI / Ant Design | UI components |
| State Management | Redux / NgRx | State handling |
| Video Player | Video.js / HLS.js | Video streaming |

#### 4.1.3 AI/ML Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Deep Learning | PyTorch 2.0 / TensorFlow 2.15 | Model training |
| Model Serving | NVIDIA Triton / TensorRT | Inference |
| Computer Vision | OpenCV 4.x | Image processing |
| Face Recognition | InsightFace / FaceNet | Face detection |
| License Plate | YOLOv8 + CRNN | LPR |

#### 4.1.4 Database Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Primary Database | PostgreSQL 16 | Transactional data |
| Time Series | InfluxDB / TimescaleDB | Metrics, events |
| Document Store | MongoDB 7.x | Metadata |
| Object Storage | MinIO / Ceph | Video files |
| Graph Database | Neo4j | Relationship data |

### 4.2 Microservices Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MICROSERVICES ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    API Gateway (Kong)                                │   │
│  │  - Rate Limiting    - Authentication    - Load Balancing            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│            ┌───────────────────────┼───────────────────────┐              │
│            ▼                       ▼                       ▼              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│  │   Video Service  │    │  Analytics      │    │   Alert         │       │
│  │   - Stream       │    │  Service        │    │   Service       │       │
│  │   - Recording    │    │  - Face         │    │   - Notification│       │
│  │   - Playback     │    │  - Vehicle      │    │   - Escalation  │       │
│  │   - Export       │    │  - Object       │    │   - History     │       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘       │
│            │                       │                       │              │
│            └───────────────────────┼───────────────────────┘              │
│                                    ▼                                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│  │  Camera         │    │  Database       │    │   User          │       │
│  │  Service        │    │  Service        │    │   Service       │       │
│  │  - Discovery    │    │  - VAHAN        │    │   - Auth        │       │
│  │  - Health       │    │  - SARTHI       │    │   - RBAC        │       │
│  │  - Configuration│    │  - eGujCop      │    │   - Audit       │       │
│  │  - Provisioning │    │  - AFIS/NAFIS   │    │   - Session     │       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 API Design

#### 4.3.1 RESTful API Endpoints

**Video Management APIs:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cameras` | GET | List all cameras |
| `/api/v1/cameras/{id}/stream` | GET | Get live stream |
| `/api/v1/cameras/{id}/recordings` | GET | Get recordings |
| `/api/v1/recordings/{id}` | GET | Get recording details |
| `/api/v1/recordings/{id}/download` | GET | Download recording |

**Analytics APIs:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/analytics/faces` | POST | Search face |
| `/api/v1/analytics/vehicles` | POST | Search vehicle |
| `/api/v1/analytics/events` | GET | Get analytics events |
| `/api/v1/analytics/alerts` | GET | Get alerts |

**Database Integration APIs:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/db/vahan/{vehicleNo}` | GET | Get vehicle details |
| `/api/v1/db/sarthi/{challanNo}` | GET | Get challan details |
| `/api/v1/db/egujcop/{criminalId}` | GET | Get criminal details |
| `/api/v1/db/afis/{fingerprintId}` | GET | Get fingerprint match |

#### 4.3.2 WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `camera.status` | Server → Client | Camera status update |
| `stream.start` | Client → Server | Start stream |
| `stream.stop` | Client → Server | Stop stream |
| `alert.new` | Server → Client | New alert |
| `analytics.event` | Server → Client | Analytics event |

---

## 5. Security Design

### 5.1 Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SECURITY ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PERIMETER SECURITY                                │   │
│  │  - Web Application Firewall (WAF)                                    │   │
│  │  - DDoS Protection                                                  │   │
│  │  - IP Whitelisting                                                  │   │
│  │  - Rate Limiting                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    NETWORK SECURITY                                 │   │
│  │  - Network Segmentation (VLAN)                                      │   │
│  │  - Firewall Rules                                                   │   │
│  │  - IDS/IPS                                                          │   │
│  │  - SSL/TLS Encryption                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    APPLICATION SECURITY                             │   │
│  │  - OAuth 2.0 / JWT Authentication                                   │   │
│  │  - Role-Based Access Control (RBAC)                                 │   │
│  │  - Input Validation                                                 │   │
│  │  - SQL Injection Protection                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DATA SECURITY                                    │   │
│  │  - Encryption at Rest (AES-256)                                     │   │
│  │  - Encryption in Transit (TLS 1.3)                                  │   │
│  │  - Data Masking                                                     │   │
│  │  - Backup Encryption                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    COMPLIANCE & AUDIT                               │   │
│  │  - Audit Logging                                                    │   │
│  │  - Compliance Monitoring (IT Act, DPDP Act)                         │   │
│  │  - Incident Response                                                │   │
│  │  - Forensic Analysis                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Authentication & Authorization

#### 5.2.1 Authentication Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │────▶│   Login     │────▶│  OAuth 2.0  │────▶│   Token     │
│   Request   │     │   Service   │     │  Provider   │     │   Service   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  Credential │     │   MFA       │     │   JWT       │
                    │  Validation │     │  Verification│     │   Generation│
                    └─────────────┘     └─────────────┘     └─────────────┘
```

#### 5.2.2 Role-Based Access Control (RBAC)

| Role | Permissions | Access Level |
|------|-------------|--------------|
| Super Admin | Full system access | All modules |
| State Admin | State-level management | All departments |
| District Admin | District-level management | District cameras |
| Department Head | Department management | Department cameras |
| Operator | Live viewing, recording | Assigned cameras |
| Analyst | Analytics, reports | Analytics modules |
| Viewer | View only | Assigned feeds |

### 5.3 Data Encryption

| Data State | Encryption Method | Key Management |
|------------|-------------------|----------------|
| At Rest | AES-256 | Hardware Security Module (HSM) |
| In Transit | TLS 1.3 | Certificate Authority |
| In Processing | Memory Encryption | Secure Enclave |
| Backups | AES-256 | Key Vault |

---

## 6. Integration Design

### 6.1 Camera Integration

#### 6.1.1 Protocol Support

| Protocol | Camera Type | Integration Method |
|----------|-------------|-------------------|
| ONVIF Profile S/T/G | IP Cameras | Direct integration |
| RTSP | IP Cameras | Stream pulling |
| RTMP | IP Cameras | Stream pushing |
| GB/T 28181 | Chinese Cameras | SIP-based |
| Analog | Analog Cameras | Encoder interface |
| SDK | Vendor-specific | Custom drivers |

#### 6.1.2 Camera Connector Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  CAMERA CONNECTOR ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Protocol Adapter Layer                      │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │   │
│  │  │  ONVIF  │  │  RTSP   │  │  RTMP   │  │  GB/T   │   │   │
│  │  │ Adapter │  │ Adapter │  │ Adapter │  │ 28181   │   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Stream Processing Layer                     │   │
│  │  - Transcoding     - Format Conversion                  │   │
│  │  - Resolution Scaling  - Frame Rate Adjustment          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Stream Output Layer                         │   │
│  │  - HLS (HTTP Live Streaming)                            │   │
│  │  - DASH (Dynamic Adaptive Streaming)                    │   │
│  │  - WebRTC (Real-time Communication)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Database Integration

#### 6.2.1 VAHAN Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    VAHAN INTEGRATION                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Request Flow                                │   │
│  │                                                          │   │
│  │  CCTV System ──▶ API Gateway ──▶ VAHAN API ──▶ Response │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Data Mapping                                │   │
│  │                                                          │   │
│  │  CCTV Data          VAHAN Data                          │   │
│  │  ─────────          ──────────                          │   │
│  │  License Plate ──▶ Vehicle Number                       │   │
│  │  Timestamp    ──▶ Registration Date                     │   │
│  │  Location     ──▶ Registered RTO                        │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Alert Triggers                              │   │
│  │                                                          │   │
│  │  - Stolen Vehicle Detected                              │   │
│  │  - Invalid Registration                                 │   │
│  │  - Expired Insurance                                    │   │
│  │  - Blacklisted Vehicle                                  │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 6.2.2 eGujCop Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                   eGujCop INTEGRATION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Integration Points                          │   │
│  │                                                          │   │
│  │  1. Criminal Database   - Face matching                  │   │
│  │  2. FIR Database        - Case linking                   │   │
│  │  3. Missing Persons     - Identification                 │   │
│  │  4. Stolen Property     - Recovery                       │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Data Exchange Format                        │   │
│  │                                                          │   │
│  │  Request:  JSON / SOAP (legacy)                         │   │
│  │  Response: JSON                                         │   │
│  │  Auth:     Digital Certificate + API Key                 │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Deployment Architecture

### 7.1 Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Master Nodes (3)                                  │   │
│  │  - API Server      - Scheduler      - Controller Manager           │   │
│  │  - etcd Cluster    - Cloud Controller Manager                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Worker Nodes (State DC)                          │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Application Namespace                                        │   │   │
│  │  │  - video-service     - analytics-service   - alert-service   │   │   │
│  │  │  - camera-service    - database-service    - user-service    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Infrastructure Namespace                                    │   │   │
│  │  │  - kafka-cluster    - redis-cluster    - elasticsearch       │   │   │
│  │  │  - postgresql       - minio            - prometheus          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Worker Nodes (District)                          │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Edge Namespace                                              │   │   │
│  │  │  - edge-service    - local-storage   - stream-processor     │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD PIPELINE                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │   Code   │───▶│  Build   │───▶│  Test    │───▶│  Scan    │             │
│  │  Commit  │    │          │    │          │    │          │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│       │               │               │               │                    │
│       ▼               ▼               ▼               ▼                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │  GitHub  │    │  Docker  │    │  Jest/   │    │  Sonar   │             │
│  │  Repo    │    │  Build   │    │  Cypress │    │  Qube    │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│                                                                              │
│       │               │               │               │                    │
│       ▼               ▼               ▼               ▼                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │  Image   │    │  Helm    │    │  Stage   │    │  Prod    │             │
│  │  Push    │    │  Chart   │    │  Deploy  │    │  Deploy  │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Monitoring & Observability

### 8.1 Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONITORING ARCHITECTURE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Metrics Collection                                │   │
│  │  - Prometheus        - Node Exporter    - Application Metrics       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Metrics Storage                                   │   │
│  │  - Thanos / Mimir     - Long-term Storage                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Visualization                                     │   │
│  │  - Grafana Dashboards  - Custom Dashboards                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Logging                                           │   │
│  │  - Fluentd / Filebeat  - Elasticsearch    - Kibana                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Tracing                                           │   │
│  │  - Jaeger / Zipkin     - Distributed Tracing                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Alerting                                          │   │
│  │  - Alertmanager        - PagerDuty / OpsGenie Integration          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Key Metrics

| Category | Metric | Threshold |
|----------|--------|-----------|
| System | CPU Usage | > 80% alert |
| System | Memory Usage | > 85% alert |
| System | Disk Usage | > 90% alert |
| Network | Bandwidth Utilization | > 70% alert |
| Application | API Response Time | > 500ms alert |
| Application | Error Rate | > 1% alert |
| Video | Stream Availability | < 99% alert |
| Video | Frame Drop Rate | > 5% alert |
| Analytics | Processing Latency | > 2s alert |
| Analytics | Model Accuracy | < 90% alert |

---

## 9. Disaster Recovery

### 9.1 DR Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DISASTER RECOVERY ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PRIMARY SITE (State DC)                           │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Active-Active Cluster                                        │   │   │
│  │  │  - Application Servers    - Database Servers                 │   │   │
│  │  │  - Storage Systems        - Network Infrastructure          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ Synchronous Replication                │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DR SITE (Alternate DC)                            │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Standby Cluster                                              │   │   │
│  │  │  - Warm Standby Servers   - Async Replication                │   │   │
│  │  │  - Backup Storage         - Network Links                    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RPO / RTO TARGETS                                 │   │
│  │                                                                      │   │
│  │  - RPO (Recovery Point Objective): 1 hour                          │   │
│  │  - RTO (Recovery Time Objective): 4 hours                          │   │
│  │  - Availability Target: 99.95%                                      │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Backup Strategy

| Data Type | Backup Frequency | Retention | Storage |
|-----------|------------------|-----------|---------|
| Database | Every 6 hours | 30 days | Offsite |
| Configuration | Daily | 90 days | Offsite |
| Video Footage | Real-time | 30 days | Distributed |
| Logs | Daily | 90 days | Offsite |
| Analytics Data | Daily | 1 year | Offsite |

---

## 10. Performance Requirements

### 10.1 Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Live Stream Latency | < 2 seconds | End-to-end |
| Playback Start Time | < 3 seconds | Time to first frame |
| Search Response Time | < 5 seconds | Metadata search |
| Analytics Processing | < 2 seconds | Per frame |
| Alert Generation | < 5 seconds | Detection to notification |
| Concurrent Users | 1000+ | Simultaneous connections |
| Concurrent Streams | 5000+ | Simultaneous streams |
| API Response Time | < 200ms | 95th percentile |

### 10.2 Scalability Targets

| Component | Current | Year 1 | Year 3 | Year 5 |
|-----------|---------|--------|--------|--------|
| Cameras | 13,000 | 20,000 | 35,000 | 50,000 |
| Storage | 5.6 PB | 10 PB | 25 PB | 50 PB |
| Users | 500 | 1,000 | 2,500 | 5,000 |
| Analytics | 1,000 | 5,000 | 15,000 | 30,000 |

---

## 11. Compliance & Standards

### 11.1 Regulatory Compliance

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| IT Act 2000 | Data protection | Encryption, access control |
| DPDP Act 2023 | Data privacy | Consent, data minimization |
| CERT-In Guidelines | Incident reporting | Automated alerts |
| NBC Standards | Camera specifications | Quality standards |

### 11.2 Industry Standards

| Standard | Applicability |
|----------|---------------|
| ONVIF Profile S/T/G | Camera integration |
| ISO 27001 | Information security |
| ISO 22301 | Business continuity |
| SOC 2 Type II | Service organization |

---

## 12. Appendix

### 12.1 Glossary

| Term | Definition |
|------|------------|
| VMS | Video Management System |
| ONVIF | Open Network Video Interface Forum |
| RTSP | Real Time Streaming Protocol |
| RBAC | Role-Based Access Control |
| DR | Disaster Recovery |
| RPO | Recovery Point Objective |
| RTO | Recovery Time Objective |

### 12.2 Reference Documents

1. Gujarat State IT Policy
2. National Police Modernization Guidelines
3. BIS Standards for CCTV
4. CERT-In Security Guidelines

---

*Document Version: 1.0*
*Prepared for: Gujarat State CCTV Integration Project*
*Date: September 2026*
*Classification: Confidential*