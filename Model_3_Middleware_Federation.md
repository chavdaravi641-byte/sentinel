# Gujarat State CCTV Integration Project
## Model 3: Middleware/Federation Layer

---

## Document Control

| Parameter | Details |
|-----------|---------|
| Document Title | Model 3 - Middleware/Federation Layer |
| Version | 1.0 |
| Date | September 2026 |
| Classification | Confidential |
| Model Type | Middleware + Federation (Cross-System Integration) |

---

## 1. Executive Summary

Model 3 proposes a **Middleware/Federation Layer** to integrate multiple departmental VMS platforms through APIs, SDKs, metadata exchange, event sharing mechanisms, or standard protocols. This enables interoperability, cross-platform communication, centralized event correlation, and unified operational workflows without replacing existing departmental systems.

**Key Value Proposition:**
- Adapter/plugin architecture for multiple VMS vendors
- Metadata exchange bus for camera and event information
- Cross-system event correlation engine
- Unified workflow and alert dashboard
- Extensible connector framework for future vendors

---

## 2. Introduction & Background

### 2.1 Current State

Different departments across Gujarat State use heterogeneous CCTV systems supplied by multiple vendors:

| Department | VMS Platform | Vendor | Camera Count | Protocol |
|------------|--------------|--------|--------------|----------|
| Home Department | Milestone XProtect | Milestone | 1,500 | ONVIF/SDK |
| Home Department | Hikvision NVR | Hikvision | 1,200 | ONVIF/RTSP |
| Home Department | Custom VMS | Local vendor | 800 | Proprietary |
| RTO | Dahua NVR | Dahua | 2,000 | ONVIF/RTSP |
| Food & Civil | Basic NVR | Multiple | 1,500 | RTSP |
| Urban Dev | Genetec Security Center | Genetec | 1,200 | ONVIF/SDK |
| Revenue | Local VMS | Various | 800 | Mixed |
| Health | Hospital VMS | Various | 600 | Mixed |
| Others | Various | Multiple | 3,400 | Mixed |

### 2.2 Problem Statement

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT PROBLEMS                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. HETEROGENEOUS VMS PLATFORMS                                              │
│     - 10+ different VMS systems                                            │
│     - Multiple vendor protocols                                            │
│     - No standard integration method                                       │
│                                                                              │
│  2. SILOED METADATA                                                          │
│     - Camera data in separate databases                                    │
│     - Event data not shared across systems                                 │
│     - No cross-system search capability                                    │
│                                                                              │
│  3. NO EVENT CORRELATION                                                     │
│     - Events in separate systems                                           │
│     - Cannot correlate related events                                      │
│     - Missed incident patterns                                             │
│                                                                              │
│  4. OPERATIONAL INEFFICIENCY                                                 │
│     - Multiple operator consoles                                           │
│     - No unified workflow                                                  │
│     - Duplicate monitoring efforts                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Solution Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 3 SOLUTION OVERVIEW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OBJECTIVE: Enable interoperability without replacing existing systems      │
│                                                                              │
│  APPROACH:                                                                   │
│  ├── Middleware layer communicates with multiple VMS                        │
│  ├── Adapters translate vendor-specific protocols                          │
│  ├── Metadata exchange bus enables data sharing                            │
│  ├── Event correlation engine links related events                         │
│  └── Unified interface for downstream applications                         │
│                                                                              │
│  KEY DIFFERENCE FROM MODEL 2:                                                │
│  - Model 2: Direct connection to each VMS/Camera                           │
│  - Model 3: Middleware/federation layer (indirect)                          │
│                                                                              │
│  SCOPE:                                                                      │
│  ✓ VMS adapter/plugin architecture                                         │
│  ✓ Metadata exchange                                                        │
│  ✓ Event correlation                                                        │
│  ✓ Unified workflow                                                         │
│  ✓ Extensible connectors                                                   │
│  ✗ NO direct camera connection (uses existing VMS)                         │
│  ✗ NO centralised recording                                                │
│  ✗ NO replacement of existing systems                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Adapter/Plugin Architecture

#### 3.1.1 Adapter Types

| Adapter Type | Description | Use Case |
|--------------|-------------|----------|
| VMS Adapter | Connects to VMS platforms | Milestone, Genetec, etc. |
| NVR Adapter | Connects to NVR devices | Hikvision, Dahua NVRs |
| Camera Adapter | Direct camera connection | ONVIF cameras |
| Protocol Adapter | Translates protocols | GB/T 28181, etc. |
| Custom Adapter | Vendor-specific integration | Proprietary systems |

#### 3.1.2 Adapter Interface

```typescript
interface VMSAdapter {
  // Connection
  connect(config: AdapterConfig): Promise<void>;
  disconnect(): Promise<void>;
  getStatus(): AdapterStatus;
  
  // Camera Operations
  getCameras(): Promise<Camera[]>;
  getCameraStream(cameraId: string): Promise<StreamInfo>;
  controlPTZ(cameraId: string, command: PTZCommand): Promise<void>;
  
  // Metadata
  getCameraMetadata(cameraId: string): Promise<CameraMetadata>;
  updateCameraMetadata(cameraId: string, metadata: CameraMetadata): Promise<void>;
  
  // Events
  subscribeEvents(callback: EventCallback): void;
  unsubscribeEvents(): void;
  
  // Recording
  getRecordings(cameraId: string, timeRange: TimeRange): Promise<Recording[]>;
  getRecordingUrl(recordingId: string): Promise<string>;
}
```

#### 3.1.3 Supported Adapters

| VMS Platform | Adapter Status | Features |
|--------------|----------------|----------|
| Milestone XProtect | Supported | Full (Live, PTZ, Recording) |
| Genetec Security Center | Supported | Full (Live, PTZ, Recording) |
| Avigilon | Supported | Full (Live, PTZ, Recording) |
| Exacq | Supported | Live, Recording |
| Hikvision NVR | Supported | Full |
| Dahua NVR | Supported | Full |
| Samsung | Supported | Live, PTZ |
| Bosch | Supported | Live, PTZ |
| Custom/Proprietary | Partial | Custom development |

### 3.2 Metadata Exchange Bus

#### 3.2.1 Metadata Types

| Metadata Type | Description | Update Frequency |
|---------------|-------------|------------------|
| Camera Info | Static camera details | On change |
| Camera Status | Online/Offline status | Real-time |
| Event Data | Detected events | Real-time |
| Alert Data | Generated alerts | Real-time |
| Analytics Data | AI/ML results | Real-time |
| Health Data | System health metrics | Every 5 min |

#### 3.2.2 Metadata Exchange Format

```json
{
  "message_id": "uuid",
  "message_type": "camera_status",
  "source_system": "milestone_xprotect",
  "timestamp": "2026-09-15T10:30:00Z",
  "payload": {
    "camera_id": "MILE-CAM-001",
    "status": "online",
    "last_seen": "2026-09-15T10:29:55Z",
    "stream_quality": "good",
    "location": {
      "latitude": 23.0225,
      "longitude": 72.5714
    }
  },
  "metadata": {
    "version": "1.0",
    "correlation_id": "uuid"
  }
}
```

#### 3.2.3 Kafka Topic Structure

```
cctv-registry/
├── camera-metadata/
│   ├── camera-created
│   ├── camera-updated
│   └── camera-deleted
├── camera-status/
│   ├── camera-online
│   ├── camera-offline
│   └── camera-health
├── events/
│   ├── motion-detected
│   ├── intrusion-detected
│   ├── plate-recognized
│   └── face-detected
├── alerts/
│   ├── alert-generated
│   ├── alert-acknowledged
│   └── alert-resolved
└── analytics/
    ├── crowd-analysis
    ├── vehicle-count
    └── behavior-analysis
```

### 3.3 Cross-System Event Correlation

#### 3.3.1 Correlation Rules

| Rule Type | Description | Example |
|-----------|-------------|---------|
| Temporal | Events within time window | Same plate at 2 cameras within 5 min |
| Spatial | Events in same location | Events at same intersection |
| Entity | Same entity across systems | Same vehicle in different VMS |
| Pattern | Sequence of events | Vehicle → Person → Event |
| Anomaly | Unusual pattern detection | Unusual movement pattern |

#### 3.3.2 Correlation Engine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EVENT CORRELATION ENGINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Event     │───▶│   Event     │───▶│   Correlation│───▶│   Output    │ │
│  │   Input     │    │   Parser    │    │   Engine     │    │   Generator │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CORRELATION WORKFLOW                                                │   │
│  │                                                                      │   │
│  │  1. Event received from VMS A (Milestone)                           │   │
│  │  2. Event normalized to standard format                             │   │
│  │  3. Query similar events in time window (5 min)                     │   │
│  │  4. Find matching events in VMS B (Genetec)                         │   │
│  │  5. Correlate events if match found                                 │   │
│  │  6. Generate correlated event                                       │   │
│  │  7. Trigger unified alert                                           │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.3 Correlation Output

```json
{
  "correlation_id": "uuid",
  "correlation_type": "temporal_spatial",
  "events": [
    {
      "event_id": "event-1",
      "source_system": "milestone",
      "camera_id": "MILE-CAM-001",
      "timestamp": "2026-09-15T10:30:00Z",
      "event_type": "plate_recognized",
      "plate_number": "GJ01AB1234"
    },
    {
      "event_id": "event-2",
      "source_system": "genetec",
      "camera_id": "GEN-CAM-005",
      "timestamp": "2026-09-15T10:32:00Z",
      "event_type": "plate_recognized",
      "plate_number": "GJ01AB1234"
    }
  ],
  "correlation_score": 0.95,
  "insight": "Vehicle GJ01AB1234 moved from SG Highway to CG Road in 2 minutes",
  "alert_generated": true,
  "alert_priority": "high"
}
```

### 3.4 Unified Workflow & Alert Dashboard

#### 3.4.1 Workflow Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Alert Triage | Prioritize and assign alerts | Mandatory |
| Incident Creation | Create incidents from alerts | Mandatory |
| Task Assignment | Assign tasks to operators | Mandatory |
| Escalation | Auto-escalation rules | Mandatory |
| Collaboration | Operator collaboration tools | Desirable |
| Audit Trail | Complete workflow audit | Mandatory |

#### 3.4.2 Alert Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  UNIFIED ALERT DASHBOARD                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ALERT SUMMARY                                                       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ Total   │ │ Critical│ │ High    │ │ Medium  │ │ Low     │     │   │
│  │  │ Today   │ │ 5       │ │ 12      │ │ 25      │ │ 100     │     │   │
│  │  │ 142     │ │ (+2)    │ │ (+5)    │ │ (+8)    │ │ (+30)   │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CORRELATED ALERTS                                                   │   │
│  │                                                                      │   │
│  │  🔴 CRITICAL | 10:30:15 | Stolen Vehicle Detected                   │   │
│  │     Source: Milestone + Genetec (Correlated)                        │   │
│  │     Plate: GJ01AB1234 | Vehicle: Maruti Swift                       │   │
│  │     [View Details] [Assign] [Escalate]                              │   │
│  │                                                                      │   │
│  │  🔴 CRITICAL | 10:28:42 | Suspect Person Identified                 │   │
│  │     Source: Hikvision NVR (Single source)                           │   │
│  │     Face Match: 92% with database                                   │   │
│  │     [View Details] [Assign] [Escalate]                              │   │
│  │                                                                      │   │
│  │  🟡 HIGH | 10:25:10 | Intrusion Detected                            │   │
│  │     Source: Dahua NVR + Milestone (Correlated)                      │   │
│  │     Location: Restricted Zone A                                     │   │
│  │     [View Details] [Assign] [Escalate]                              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.5 Extensible Connector Framework

#### 3.5.1 Connector Development Kit (CDK)

| Component | Description |
|-----------|-------------|
| SDK | Software Development Kit for adapters |
| Template | Adapter development template |
| Documentation | Integration guide |
| Test Suite | Adapter testing tools |
| Certification | Adapter certification program |

#### 3.5.2 Connector Registration

```json
{
  "connector_id": "milestone-connector-v2",
  "name": "Milestone XProtect Connector",
  "version": "2.0.0",
  "vendor": "Milestone Systems",
  "supported_versions": ["2022", "2023", "2024"],
  "capabilities": [
    "live_stream",
    "ptz_control",
    "recording_access",
    "event_subscription",
    "metadata_exchange"
  ],
  "configuration_schema": {
    "server_url": "string",
    "username": "string",
    "password": "string",
    "api_version": "string"
  },
  "certification_date": "2026-01-15",
  "certification_expiry": "2027-01-15"
}
```

---

## 4. Technical Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 3 SYSTEM ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DEPARTMENTAL VMS PLATFORMS                        │   │
│  │                                                                      │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │Milestone│ │Genetec  │ │Hikvision│ │Dahua    │ │Custom   │     │   │
│  │  │XProtect │ │Security │ │NVR      │ │NVR      │ │VMS      │     │   │
│  │  │         │ │Center   │ │         │ │         │ │         │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ADAPTER/CONNECTOR LAYER                           │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Adapter Framework                                           │   │   │
│  │  │  - Milestone Adapter    - Genetec Adapter                    │   │   │
│  │  │  - Hikvision Adapter    - Dahua Adapter                      │   │   │
│  │  │  - Custom Adapters      - Protocol Adapters                  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FEDERATION MIDDLEWARE                              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  API Gateway  │  │  Message     │  │  Event       │              │   │
│  │  │  (Kong)       │  │  Router      │  │  Processor   │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Auth        │  │  Orchestration│  │  Workflow    │              │   │
│  │  │  Service     │  │  Engine       │  │  Engine      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    EVENT & METADATA BUS                              │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Apache Kafka Cluster                                        │   │   │
│  │  │  - Camera Metadata Topics                                    │   │   │
│  │  │  - Event Topics                                              │   │   │
│  │  │  - Alert Topics                                              │   │   │
│  │  │  - Analytics Topics                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DOWNSTREAM APPLICATIONS                           │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Unified     │  │  Analytics   │  │  Dashboard   │              │   │
│  │  │  Dashboard   │  │  Engine      │  │  & Reports   │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Middleware Components

#### 4.2.1 API Gateway (Kong)

| Feature | Description |
|---------|-------------|
| Rate Limiting | Prevent API abuse |
| Authentication | JWT, OAuth 2.0 |
| Load Balancing | Distribute traffic |
| SSL Termination | HTTPS handling |
| Logging | Request/response logging |
| Plugins | Extensible functionality |

#### 4.2.2 Message Router

| Feature | Description |
|---------|-------------|
| Topic Management | Create/manage Kafka topics |
| Message Routing | Route messages to consumers |
| Message Transformation | Convert message formats |
| Dead Letter Queue | Handle failed messages |
| Message Replay | Replay historical messages |

#### 4.2.3 Event Processor

| Feature | Description |
|---------|-------------|
| Event Parsing | Parse different event formats |
| Event Normalization | Convert to standard format |
| Event Enrichment | Add metadata |
| Event Correlation | Link related events |
| Event Storage | Store events for replay |

### 4.3 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Middleware** | | | |
| API Gateway | Kong | 3.x | API management |
| Message Queue | Apache Kafka | 3.x | Event streaming |
| Service Mesh | Istio | 1.20+ | Service communication |
| **Backend** | | | |
| Runtime | Java 17 / Go 1.21 | LTS | Server |
| Framework | Spring Boot / Gin | 3.x / 1.21 | API framework |
| **Database** | | | |
| Primary | PostgreSQL | 16 | Data storage |
| Cache | Redis | 7.x | Caching |
| Search | Elasticsearch | 8.x | Event search |
| **Monitoring** | | | |
| Metrics | Prometheus | 2.x | Metrics |
| Visualization | Grafana | 10.x | Dashboards |
| Logging | ELK Stack | 8.x | Log management |

---

## 5. User Interface Design

### 5.1 Federation Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FEDERATION MIDDLEWARE DASHBOARD                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SYSTEM STATUS                                                       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ Milestone│ │ Genetec │ │Hikvision│ │  Dahua  │ │ Custom  │     │   │
│  │  │ 🟢      │ │ 🟢      │ │ 🟢      │ │ 🟡      │ │ 🔴      │     │   │
│  │  │ 1,500   │ │ 1,200   │ │ 1,200   │ │ 2,000   │ │ 800     │     │   │
│  │  │ cameras │ │ cameras │ │ cameras │ │ cameras │ │ cameras │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CONNECTOR STATUS                                                    │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Connector        │ Status  │ Messages/sec │ Errors │ Uptime │   │   │
│  │  │  ─────────────────┼─────────┼──────────────┼────────┼────────│   │   │
│  │  │  Milestone v2     │ 🟢 Active│ 150          │ 0      │ 99.99% │   │   │
│  │  │  Genetec v3       │ 🟢 Active│ 120          │ 0      │ 99.98% │   │   │
│  │  │  Hikvision v1     │ 🟢 Active│ 180          │ 2      │ 99.95% │   │   │
│  │  │  Dahua v1         │ 🟡 Degraded│ 90        │ 15     │ 98.50% │   │   │
│  │  │  Custom v1        │ 🔴 Error │ 0            │ 500    │ 0.00%  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  EVENT CORRELATION                                                   │   │
│  │                                                                      │   │
│  │  Today's Correlations: 45                                           │   │
│  │  Cross-system Events: 120                                           │   │
│  │  Correlation Accuracy: 94%                                          │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Connector Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CONNECTOR MANAGEMENT                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  AVAILABLE CONNECTORS                                                │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Milestone XProtect Connector v2.0                          │   │   │
│  │  │  - Supported Versions: 2022, 2023, 2024                     │   │   │
│  │  │  - Capabilities: Live, PTZ, Recording, Events               │   │   │
│  │  │  - Status: ✅ Installed                                      │   │   │
│  │  │  [Configure] [Update] [Uninstall]                           │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Genetec Security Center Connector v3.0                     │   │   │
│  │  │  - Supported Versions: 5.10, 5.11, 5.12                     │   │   │
│  │  │  - Capabilities: Live, PTZ, Recording, Events               │   │   │
│  │  │  - Status: ✅ Installed                                      │   │   │
│  │  │  [Configure] [Update] [Uninstall]                           │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Avigilon Connector v1.5                                    │   │   │
│  │  │  - Supported Versions: 7.x, 8.x                            │   │   │
│  │  │  - Capabilities: Live, Recording, Events                    │   │   │
│  │  │  - Status: 📦 Available                                     │   │   │
│  │  │  [Install] [Documentation]                                  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. API Documentation

### 6.1 Connector APIs

#### 6.1.1 List Connectors

```
GET /api/v1/connectors

Response:
{
  "success": true,
  "data": {
    "connectors": [
      {
        "id": "milestone-connector-v2",
        "name": "Milestone XProtect Connector",
        "version": "2.0.0",
        "status": "active",
        "cameras_count": 1500
      }
    ]
  }
}
```

#### 6.1.2 Register Connector

```
POST /api/v1/connectors

Request:
{
  "connector_id": "genetec-connector-v3",
  "config": {
    "server_url": "https://genetec-server:443",
    "username": "admin",
    "password": "encrypted_password",
    "api_version": "5.12"
  }
}

Response:
{
  "success": true,
  "data": {
    "connector_id": "genetec-connector-v3",
    "status": "registered",
    "cameras_discovered": 1200
  }
}
```

### 6.2 Event APIs

#### 6.2.1 Subscribe to Events

```
POST /api/v1/events/subscribe

Request:
{
  "event_types": ["plate_recognized", "intrusion_detected"],
  "source_systems": ["milestone", "genetec"],
  "callback_url": "https://your-server.com/webhook",
  "filters": {
    "district": "ahmedabad"
  }
}

Response:
{
  "success": true,
  "data": {
    "subscription_id": "uuid",
    "status": "active"
  }
}
```

#### 6.2.2 Get Correlated Events

```
GET /api/v1/events/correlated

Query Parameters:
- time_window (default: 300 seconds)
- correlation_type (temporal, spatial, entity)
- min_score (default: 0.7)

Response:
{
  "success": true,
  "data": {
    "correlations": [
      {
        "correlation_id": "uuid",
        "events": [...],
        "correlation_score": 0.95,
        "insight": "Vehicle moved across 3 cameras in 5 minutes"
      }
    ]
  }
}
```

---

## 7. Deliverables

| # | Deliverable | Description | Acceptance Criteria |
|---|-------------|-------------|---------------------|
| 1 | **Working Middleware** | Federate 2+ different systems | Systems connected |
| 2 | **Unified Event Dashboard** | Cross-system events | Events correlated |
| 3 | **Adapter Architecture** | Documentation | Complete design |
| 4 | **Federated Analytics** | Sample report | Report generated |
| 5 | **Connector Framework** | CDK for vendors | SDK + documentation |
| 6 | **API Documentation** | Complete API docs | OpenAPI/Swagger |

---

## 8. Implementation Plan

| Phase | Duration | Activities |
|-------|----------|------------|
| Phase 1 | Month 1-4 | Middleware core development |
| Phase 2 | Month 5-8 | Adapter development (Milestone, Genetec) |
| Phase 3 | Month 9-12 | Event correlation engine |
| Phase 4 | Month 13-16 | Dashboard, workflow engine |
| Phase 5 | Month 17-20 | Testing, pilot |
| Phase 6 | Month 21-24 | Full deployment |

---

*Document Version: 1.0*
*Date: September 2026*
*Model: 3 - Middleware/Federation Layer*