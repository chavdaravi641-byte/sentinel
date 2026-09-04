# Gujarat State CCTV Integration Project
## Model 2: Unified Viewing Platform

---

## Document Control

| Parameter | Details |
|-----------|---------|
| Document Title | Model 2 - Unified Viewing Platform |
| Version | 1.0 |
| Date | September 2026 |
| Classification | Confidential |
| Model Type | Viewing + Metadata (No Central Storage) |

---

## 1. Executive Summary

Model 2 proposes a **Unified Viewing Platform** through which CCTV feeds from different departmental systems can be accessed through a single interface without disturbing existing infrastructure. Existing departmental VMS/storage systems continue to operate independently.

**Key Value Proposition:**
- Single interface for all camera feeds
- No replacement of existing VMS systems
- ANPR and metadata generation
- Configurable video walls
- Real-time alerts

---

## 2. Introduction & Background

### 2.1 Current State

Multiple departments currently operate independent CCTV systems through their own Video Management Systems (VMS):

| Department | VMS Platform | Camera Count | Current Access Method |
|------------|--------------|--------------|----------------------|
| Home Department | Multiple vendors | 3,500 | 5 separate VMS |
| RTO | Hikvision NVR | 2,000 | Local viewer |
| Food & Civil Supplies | Limited VMS | 1,500 | Manual access |
| Urban Development | City-specific | 1,200 | Multiple systems |
| Revenue | Basic NVR | 800 | Local access |
| Health | Hospital VMS | 600 | Individual systems |
| Others | Various | 3,400 | Fragmented |

### 2.2 Problem Statement

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT PROBLEMS                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. MULTIPLE VIEWER SYSTEMS                                                  │
│     - Each department has separate VMS                                      │
│     - Command centre needs multiple screens                                │
│     - No single view of all cameras                                        │
│                                                                              │
│  2. OPERATIONAL COMPLEXITY                                                   │
│     - Operators need to switch between systems                             │
│     - Training required for each VMS                                       │
│     - Slow response to incidents                                           │
│                                                                              │
│  3. NO UNIFIED METADATA                                                      │
│     - ANPR data in separate systems                                        │
│     - Cannot search across departments                                     │
│     - No cross-system analytics                                             │
│                                                                              │
│  4. NO ALERT CORRELATION                                                     │
│     - Alerts in separate systems                                           │
│     - Cannot correlate events across cameras                               │
│     - Missed incident detection                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Solution Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 2 SOLUTION OVERVIEW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OBJECTIVE: Unified viewing without replacing existing systems              │
│                                                                              │
│  APPROACH:                                                                   │
│  ├── Connect directly to departmental VMS/Cameras                          │
│  ├── Use RTSP, ONVIF, vendor SDKs, or APIs                                │
│  ├── Relay streams to unified interface                                    │
│  ├── Generate metadata (ANPR, events)                                     │
│  └── Provide single control room view                                     │
│                                                                              │
│  SCOPE:                                                                      │
│  ✓ Live feed viewing                                                       │
│  ✓ ANPR metadata generation                                                │
│  ✓ Event tagging                                                           │
│  ✓ Configurable video walls                                                │
│  ✓ Searchable records                                                      │
│  ✗ NO centralised recording                                                │
│  ✗ NO replacement of existing VMS                                          │
│  ✗ NO middleware/federation layer                                          │
│                                                                              │
│  KEY DIFFERENCE FROM MODEL 3:                                               │
│  - Model 2: Direct connection to each VMS                                  │
│  - Model 3: Middleware/federation layer                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Feed Aggregation

#### 3.1.1 Protocol Support

| Protocol | Description | Use Case | Priority |
|----------|-------------|----------|----------|
| RTSP | Real Time Streaming Protocol | IP cameras | Mandatory |
| ONVIF | Open Network Video Interface Forum | Standard cameras | Mandatory |
| RTMP | Real Time Messaging Protocol | Streaming servers | Desirable |
| HLS | HTTP Live Streaming | Web browsers | Mandatory |
| WebRTC | Web Real-Time Communication | Low-latency | Desirable |
| Vendor SDK | Proprietary SDKs | Specific vendors | Mandatory |

#### 3.1.2 Camera Integration Matrix

| Camera Brand | Protocol | Integration Method | Status |
|--------------|----------|-------------------|--------|
| Hikvision | ONVIF, RTSP, SDK | Direct | Supported |
| Dahua | ONVIF, RTSP, SDK | Direct | Supported |
| Axis | ONVIF, VAPIX | Direct | Supported |
| CP Plus | ONVIF, RTSP | Direct | Supported |
| Samsung | ONVIF, RTSP | Direct | Supported |
| Bosch | ONVIF, HTTP | Direct | Supported |
| Honeywell | SDK | Custom | Supported |
| Sony | ONVIF, CGI | Direct | Supported |
| Panasonic | SDK | Custom | Supported |

#### 3.1.3 VMS Integration

| VMS Platform | Integration Method | Features |
|--------------|-------------------|----------|
| Milestone | VMS Bridge | Live, playback |
| Genetec | VMS Bridge | Live, playback |
| Avigilon | VMS Bridge | Live, playback |
| Exacq | VMS Bridge | Live, playback |
| Hikvision NVR | Direct RTSP | Live, playback |
| Dahua NVR | Direct RTSP | Live, playback |

### 3.2 Stream Management

#### 3.2.1 Stream Processing

| Feature | Description | Priority |
|---------|-------------|----------|
| Transcoding | Convert to web-friendly format | Mandatory |
| Rate Adapting | Adjust bandwidth per stream | Mandatory |
| Failover | Automatic stream recovery | Mandatory |
| Load Balancing | Distribute stream load | Mandatory |
| Quality Control | Monitor stream quality | Mandatory |

#### 3.2.2 Stream Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STREAM ARCHITECTURE                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Camera    │───▶│   Stream    │───▶│   Transcode │───▶│   Web       │ │
│  │   Source    │    │   Ingest    │    │   Server    │    │   Player    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   RTSP      │    │   HLS       │    │   WebRTC    │    │   MSE       │ │
│  │   Stream    │    │   Segment   │    │   Relay     │    │   Player    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 ANPR (Automatic Number Plate Recognition)

#### 3.3.1 ANPR Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Plate Detection | Detect plates in video | Mandatory |
| Character Recognition | Read plate characters | Mandatory |
| Multi-country Plates | Indian plate formats | Mandatory |
| Confidence Score | Recognition confidence | Mandatory |
| Real-time Processing | < 1 second latency | Mandatory |
| Batch Processing | Process recorded video | Mandatory |

#### 3.3.2 ANPR Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANPR INTEGRATION                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Camera    │───▶│   ANPR      │───▶│   Database  │───▶│   Alert     │ │
│  │   Feed      │    │   Engine    │    │   Storage   │    │   System    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ANPR WORKFLOW                                      │   │
│  │                                                                      │   │
│  │  1. Video frame captured                                            │   │
│  │  2. Plate region detected                                           │   │
│  │  3. Characters extracted                                            │   │
│  │  4. Plate number formatted                                          │   │
│  │  5. Database lookup (VAHAN, SARTHI)                                 │   │
│  │  6. Alert if match found                                            │   │
│  │  7. Metadata stored                                                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.3 ANPR Output Format

```json
{
  "plate_number": "GJ01AB1234",
  "confidence": 0.95,
  "timestamp": "2026-09-15T10:30:00Z",
  "camera_id": "CAM-AHM-001",
  "location": {
    "latitude": 23.0225,
    "longitude": 72.5714,
    "address": "SG Highway Junction"
  },
  "vehicle_info": {
    "make": "Maruti Suzuki",
    "model": "Swift",
    "color": "White",
    "registration_date": "2023-05-15",
    "owner_name": "Ramesh Patel",
    "registration_state": "Gujarat"
  },
  "image_url": "/api/v1/images/plate-uuid.jpg",
  "thumbnail_url": "/api/v1/thumbnails/plate-uuid.jpg"
}
```

### 3.4 Event Tagging & Indexing

#### 3.4.1 Event Types

| Event Type | Description | Trigger |
|------------|-------------|---------|
| Vehicle Detected | Vehicle enters zone | Motion detection |
| Plate Recognized | ANPR detects plate | ANPR engine |
| Suspect Vehicle | Match with database | VAHAN/SARTHI |
| Intrusion | Unauthorized entry | Motion in zone |
| Loitering | Person lingers | Behavior analysis |
| Object Left | Abandoned object | Object detection |
| Crowd Forming | Density increase | Crowd analysis |

#### 3.4.2 Event Metadata

```json
{
  "event_id": "uuid",
  "event_type": "vehicle_detected",
  "timestamp": "2026-09-15T10:30:00Z",
  "camera_id": "CAM-AHM-001",
  "confidence": 0.92,
  "metadata": {
    "plate_number": "GJ01AB1234",
    "vehicle_color": "White",
    "vehicle_type": "Sedan"
  },
  "tags": ["traffic", "vehicle", "ahmedabad"],
  "related_events": ["event-uuid-1", "event-uuid-2"]
}
```

### 3.5 Video Wall Configuration

#### 3.5.1 Layout Options

| Layout | Cameras | Use Case |
|--------|---------|----------|
| 1x1 | 1 | Single camera focus |
| 2x2 | 4 | Small area monitoring |
| 3x3 | 9 | Medium area monitoring |
| 4x4 | 16 | Large area monitoring |
| 5x5 | 25 | Command center |
| Custom | Any | Custom layouts |
| Tour | Sequential | Camera patrol |

#### 3.5.2 Video Wall Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Drag & Drop | Add cameras by dragging | Mandatory |
| Resize Panels | Adjust panel sizes | Mandatory |
| Full Screen | Expand single panel | Mandatory |
| Snapshot | Capture current frame | Mandatory |
| Record | Manual recording trigger | Mandatory |
| PTZ Control | Control PTZ cameras | Mandatory |
| Audio | Listen to camera audio | Desirable |
| Multi-monitor | Spread across monitors | Mandatory |

#### 3.5.3 Video Wall Interface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  VIDEO WALL - Layout: Ahmedabad City Monitoring                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────┬───────────────────────┬───────────────────────┐ │
│  │                       │                       │                       │ │
│  │   CAM-AHM-001        │   CAM-AHM-002        │   CAM-AHM-003        │ │
│  │   SG Highway          │   CG Road             │   Ashram Road         │ │
│  │   🟢 Live             │   🟢 Live             │   🟡 Low Signal       │ │
│  │                       │                       │                       │ │
│  └───────────────────────┴───────────────────────┴───────────────────────┘ │
│                                                                              │
│  ┌───────────────────────┬───────────────────────┬───────────────────────┐ │
│  │                       │                       │                       │ │
│  │   CAM-AHM-004        │   CAM-AHM-005        │   CAM-AHM-006        │ │
│  │   Navrangpura         │   Satellite           │   Bodakdev            │ │
│  │   🟢 Live             │   🔴 Offline          │   🟢 Live             │ │
│  │                       │                       │                       │ │
│  └───────────────────────┴───────────────────────┴───────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CONTROLS: [Add Camera] [Remove] [Save Layout] [PTZ] [Snapshot]   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 Alert System

#### 3.6.1 Alert Types

| Alert Type | Description | Priority |
|------------|-------------|----------|
| Suspect Vehicle | Match with database | Critical |
| Stolen Vehicle | Match with stolen list | Critical |
| Wanted Person | Face match with database | Critical |
| Intrusion | Unauthorized zone entry | High |
| Camera Offline | Camera goes offline | Medium |
| Low Storage | Storage running low | Low |

#### 3.6.2 Alert Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ALERT WORKFLOW                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Event     │───▶│   Alert     │───▶│   Notify    │───▶│   Action    │ │
│  │   Detected  │    │   Generate  │    │   Users     │    │   Required  │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  NOTIFICATION CHANNELS                                               │   │
│  │                                                                      │   │
│  │  - Dashboard popup                                                   │   │
│  │  - Email notification                                                │   │
│  │  - SMS alert                                                         │   │
│  │  - Mobile push notification                                          │   │
│  │  - Audio alert in control room                                       │   │
│  │  - WhatsApp message (optional)                                       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.6.3 Alert Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ALERTS DASHBOARD                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ALERT SUMMARY                                                       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ Total   │ │ Critical│ │ High    │ │ Medium  │ │ Low     │     │   │
│  │  │ Today   │ │ 5       │ │ 12      │ │ 25      │ │ 100     │     │   │
│  │  │ 142     │ │         │ │         │ │         │ │         │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  RECENT ALERTS                                                       │   │
│  │                                                                      │   │
│  │  🔴 CRITICAL | 10:30:15 | CAM-AHM-001 | Stolen Vehicle | GJ01XX9999│   │
│  │  🔴 CRITICAL | 10:28:42 | CAM-SRT-045 | Suspect Person | Face Match│   │
│  │  🟡 HIGH     | 10:25:10 | CAM-VAD-012 | Intrusion      | Zone A   │   │
│  │  🟢 MEDIUM   | 10:20:00 | CAM-RAJ-008 | Camera Offline | 2 hours  │   │
│  │                                                                      │   │
│  │  [View All] [Export] [Acknowledge] [Escalate]                       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.7 Search & Playback

#### 3.7.1 Search Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Time-based Search | Search by time range | Mandatory |
| Camera Search | Search by camera | Mandatory |
| Event Search | Search by event type | Mandatory |
| Plate Search | Search by plate number | Mandatory |
| Location Search | Search by location | Mandatory |
| Advanced Search | Multiple criteria | Mandatory |

#### 3.7.2 Playback Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Timeline Navigation | Scrub through time | Mandatory |
| Speed Control | 0.25x to 16x | Mandatory |
| Frame-by-frame | Step through frames | Mandatory |
| Multi-camera Sync | Sync playback | Mandatory |
| Export | Download clip | Mandatory |
| Bookmark | Mark important moments | Mandatory |

---

## 4. Technical Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 2 SYSTEM ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DEPARTMENTAL SOURCES                              │   │
│  │                                                                      │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ Home    │ │ RTO     │ │ Food    │ │ Urban   │ │ Others  │     │   │
│  │  │ Dept    │ │         │ │ Civil   │ │ Dev     │ │         │     │   │
│  │  │ VMS     │ │ NVR     │ │ VMS     │ │ VMS     │ │ VMS     │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    STREAM INGESTION                                  │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Protocol Adapters                                           │   │   │
│  │  │  - RTSP Adapter    - ONVIF Adapter    - SDK Adapters         │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Stream Processing                                           │   │   │
│  │  │  - Transcoding    - Load Balancing    - Failover            │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    UNIFIED PLATFORM                                  │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Stream      │  │  ANPR        │  │  Alert       │              │   │
│  │  │  Gateway     │  │  Engine      │  │  Service     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Metadata    │  │  Search      │  │  User        │              │   │
│  │  │  Store       │  │  Engine      │  │  Service     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    USER INTERFACE                                    │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Web         │  │  Mobile      │  │  Control     │              │   │
│  │  │  Dashboard   │  │  App         │  │  Room View   │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Stream Gateway

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STREAM GATEWAY ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INGESTION LAYER                                   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  RTSP Client                                                 │   │   │
│  │  │  - Connection pooling                                        │   │   │
│  │  │  - Reconnection handling                                     │   │   │
│  │  │  - Stream validation                                         │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  ONVIF Client                                               │   │   │
│  │  │  - Device discovery                                          │   │   │
│  │  │  - Profile management                                        │   │   │
│  │  │  - PTZ control                                               │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PROCESSING LAYER                                  │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  FFmpeg / GStreamer                                          │   │   │
│  │  │  - Transcoding (H.264 → H.265, VP9)                         │   │   │
│  │  │  - Resolution scaling                                        │   │   │
│  │  │  - Frame rate adjustment                                     │   │   │
│  │  │  - Audio extraction                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OUTPUT LAYER                                      │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  HLS Segmenter                                               │   │   │
│  │  │  - Segment duration: 2 seconds                               │   │   │
│  │  │  - Multiple quality levels                                   │   │   │
│  │  │  - CDN distribution                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  WebRTC Gateway                                              │   │   │
│  │  │  - Low-latency streaming                                     │   │   │
│  │  │  - Peer connection management                                │   │   │
│  │  │  - Adaptive bitrate                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 ANPR Engine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANPR ENGINE ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INPUT PROCESSING                                  │   │
│  │                                                                      │   │
│  │  Video Frame ──▶ Pre-processing ──▶ Enhancement ──▶ Normalization   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PLATE DETECTION                                   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  YOLO-based Detection                                        │   │   │
│  │  │  - Region of Interest (ROI) extraction                       │   │   │
│  │  │  - Plate boundary detection                                  │   │   │
│  │  │  - Confidence scoring                                        │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CHARACTER RECOGNITION                             │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  CRNN + CTC                                                  │   │   │
│  │  │  - Character segmentation                                    │   │   │
│  │  │  - Character recognition                                     │   │   │
│  │  │  - Sequence decoding                                         │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST-PROCESSING                                   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - Format validation (Indian plate formats)                  │   │   │
│  │  │  - Confidence filtering                                      │   │   │
│  │  │  - Duplicate removal                                         │   │   │
│  │  │  - Database lookup                                           │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Streaming** | | | |
| RTSP Client | FFmpeg | 6.x | Stream ingestion |
| Transcoding | FFmpeg / GStreamer | 6.x / 1.22.x | Format conversion |
| HLS Server | Nginx + HLS Module | 1.24+ | HLS delivery |
| WebRTC | Janus / mediasoup | Latest | Low-latency |
| **AI/ML** | | | |
| ANPR Engine | YOLOv8 + CRNN | Latest | Plate recognition |
| Model Serving | TensorRT | 8.x | GPU inference |
| **Backend** | | | |
| Runtime | Node.js | 20 LTS | Server |
| Framework | Express.js | 4.x | API |
| Message Queue | Apache Kafka | 3.x | Event streaming |
| **Database** | | | |
| Primary | PostgreSQL | 16 | Data storage |
| Search | Elasticsearch | 8.x | Metadata search |
| Cache | Redis | 7.x | Session cache |
| **Frontend** | | | |
| Framework | React.js | 18.x | Web app |
| Video Player | Video.js | 8.x | Video playback |
| UI Library | Ant Design | 5.x | UI components |

---

## 5. User Interface Design

### 5.1 Main Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  UNIFIED VIEWING PLATFORM - Gujarat State                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  HEADER: [Logo] [Search: Camera/Plate/Location] [Alerts(5)] [User] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────┐ ┌────────────────────────────────────────────────────────┐ │
│  │            │ │                                                          │ │
│  │  SIDEBAR   │ │  VIDEO WALL (4x4 Grid)                                  │ │
│  │            │ │                                                          │ │
│  │  - Live    │ │  ┌──────────┬──────────┬──────────┬──────────┐        │ │
│  │  - Search  │ │  │ CAM-001  │ CAM-002  │ CAM-003  │ CAM-004  │        │ │
│  │  - ANPR    │ │  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │ 🔴 Off   │        │ │
│  │  - Alerts  │ │  ├──────────┼──────────┼──────────┼──────────┤        │ │
│  │  - Reports │ │  │ CAM-005  │ CAM-006  │ CAM-007  │ CAM-008  │        │ │
│  │  - Settings│ │  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │        │ │
│  │            │ │  ├──────────┼──────────┼──────────┼──────────┤        │ │
│  │            │ │  │ CAM-009  │ CAM-010  │ CAM-011  │ CAM-012  │        │ │
│  │            │ │  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │        │ │
│  │            │ │  ├──────────┼──────────┼──────────┼──────────┤        │ │
│  │            │ │  │ CAM-013  │ CAM-014  │ CAM-015  │ CAM-016  │        │ │
│  │            │ │  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │ 🟢 Live  │        │ │
│  │            │ │  └──────────┴──────────┴──────────┴──────────┘        │ │
│  │            │ │                                                          │ │
│  │            │ │  CONTROLS: [Layout] [Add Camera] [PTZ] [Snapshot]     │ │
│  └────────────┘ └────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  QUICK STATS: [Total Cameras: 13,000] [Online: 11,500] [Alerts: 5] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 ANPR Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ANPR DASHBOARD                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SEARCH PANEL                                                       │   │
│  │  Plate: [GJ01____] [Search] [Advanced]                             │   │
│  │  Date Range: [2026-09-01] to [2026-09-15]                          │   │
│  │  Camera: [All Ahmedabad ▼]                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  RECOGNITION RESULTS                                                │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  [Image] GJ01AB1234 | 15-Sep-2026 10:30:15 | CAM-AHM-001   │   │   │
│  │  │           Confidence: 98% | Location: SG Highway Junction    │   │   │
│  │  │           Vehicle: Maruti Swift | Color: White               │   │   │
│  │  │           [View on Map] [Track History] [Export]             │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  [Image] GJ01AB1234 | 15-Sep-2026 09:45:22 | CAM-AHM-003   │   │   │
│  │  │           Confidence: 95% | Location: Ashram Road           │   │   │
│  │  │           [View on Map] [Track History] [Export]             │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STATS: [Today: 45,000 plates] [Matched: 120] [Alerts: 5]          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. API Documentation

### 6.1 Stream APIs

#### 6.1.1 Get Stream URL

```
GET /api/v1/streams/{camera_id}/url

Response:
{
  "success": true,
  "data": {
    "camera_id": "CAM-AHM-001",
    "hls_url": "http://stream.gujaratcctv.gov.in/cameras/CAM-AHM-001.m3u8",
    "webrtc_url": "webrtc://stream.gujaratcctv.gov.in/cameras/CAM-AHM-001",
    "rtsp_url": "rtsp://internal/CAM-AHM-001",
    "quality": {
      "resolution": "1920x1080",
      "fps": 25,
      "bitrate": "4 Mbps"
    }
  }
}
```

#### 6.1.2 Start Stream

```
POST /api/v1/streams/{camera_id}/start

Request:
{
  "quality": "high",
  "protocol": "hls"
}

Response:
{
  "success": true,
  "data": {
    "stream_id": "uuid",
    "status": "started",
    "url": "http://stream.gujaratcctv.gov.in/cameras/CAM-AHM-001.m3u8"
  }
}
```

### 6.2 ANPR APIs

#### 6.2.1 Search by Plate

```
GET /api/v1/anpr/search

Query Parameters:
- plate_number (required)
- start_date
- end_date
- camera_id
- limit (default: 100)

Response:
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "uuid",
        "plate_number": "GJ01AB1234",
        "confidence": 0.98,
        "timestamp": "2026-09-15T10:30:00Z",
        "camera_id": "CAM-AHM-001",
        "location": {...},
        "vehicle_info": {...},
        "image_url": "/api/v1/images/uuid.jpg"
      }
    ],
    "total": 15
  }
}
```

#### 6.2.2 Track Vehicle

```
GET /api/v1/anpr/track/{plate_number}

Query Parameters:
- start_date
- end_date

Response:
{
  "success": true,
  "data": {
    "plate_number": "GJ01AB1234",
    " sightings": [
      {
        "timestamp": "2026-09-15T10:30:00Z",
        "camera_id": "CAM-AHM-001",
        "location": {...}
      },
      {
        "timestamp": "2026-09-15T09:45:00Z",
        "camera_id": "CAM-AHM-003",
        "location": {...}
      }
    ],
    "route": {
      "type": "LineString",
      "coordinates": [...]
    }
  }
}
```

### 6.3 Alert APIs

#### 6.3.1 Get Alerts

```
GET /api/v1/alerts

Query Parameters:
- priority (critical, high, medium, low)
- status (new, acknowledged, resolved)
- start_date
- end_date
- limit

Response:
{
  "success": true,
  "data": {
    "alerts": [
      {
        "id": "uuid",
        "type": "stolen_vehicle",
        "priority": "critical",
        "timestamp": "2026-09-15T10:30:00Z",
        "camera_id": "CAM-AHM-001",
        "plate_number": "GJ01AB1234",
        "status": "new"
      }
    ],
    "total": 25
  }
}
```

---

## 7. Deliverables

### 7.1 Deliverables Checklist

| # | Deliverable | Description | Acceptance Criteria |
|---|-------------|-------------|---------------------|
| 1 | **Unified Viewer** | Single interface for all feeds | 2+ different systems connected |
| 2 | **ANPR Demonstration** | Live/recorded ANPR | 95%+ accuracy |
| 3 | **Metadata Dashboard** | Searchable records | All fields searchable |
| 4 | **Video Wall** | Configurable layouts | Multiple layouts supported |
| 5 | **Alert System** | Real-time alerts | Alerts generated correctly |
| 6 | **Architecture Doc** | Technical documentation | Complete architecture |
| 7 | **API Documentation** | Complete API docs | OpenAPI/Swagger spec |
| 8 | **User Manual** | End-user documentation | Complete user guide |

---

## 8. Integration Points

### 8.1 Model 1 Integration

| Data | Flow | Frequency |
|------|------|-----------|
| Camera Metadata | Model 1 → Model 2 | Real-time |
| Camera Status | Model 1 → Model 2 | Real-time |
| Location Data | Model 1 → Model 2 | On-demand |

### 8.2 Database Integration

| Database | Integration | Data Flow |
|----------|-------------|-----------|
| VAHAN | API | Vehicle lookup |
| SARTHI | API | Challan lookup |

---

## 9. Implementation Plan

| Phase | Duration | Activities |
|-------|----------|------------|
| Phase 1 | Month 1-3 | Stream gateway development |
| Phase 2 | Month 4-6 | ANPR engine integration |
| Phase 3 | Month 7-9 | UI development, video wall |
| Phase 4 | Month 10-12 | Testing, pilot deployment |
| Phase 5 | Month 13-15 | Full deployment |

---

## 10. Success Metrics

| Metric | Target |
|--------|--------|
| Stream Availability | 99.5% |
| ANPR Accuracy | 95%+ |
| Alert Response Time | < 5 seconds |
| User Satisfaction | 4.5/5 rating |

---

*Document Version: 1.0*
*Date: September 2026*
*Model: 2 - Unified Viewing Platform*