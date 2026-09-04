# Gujarat State CCTV Integration Project
## Model 1: Centralised CCTV Registry & GIS-Based Mapping Platform

---

## Document Control

| Parameter | Details |
|-----------|---------|
| Document Title | Model 1 - CCTV Registry & GIS Platform |
| Version | 1.0 |
| Date | September 2026 |
| Classification | Confidential |
| Model Type | Foundational (Registry + GIS) |

---

## 1. Executive Summary

Model 1 proposes the development of a **Centralised CCTV Registry and GIS-Based Mapping Platform** for onboarding and maintaining camera-related metadata across all 26 government departments. This foundational model creates a unified inventory and visibility layer without involving centralised live video streaming or recording.

**Key Value Proposition:**
- Unified camera inventory across 26 departments
- GIS-based visual mapping of all assets
- Gap analysis for coverage planning
- Foundation for Models 2, 3, and 4 integration

---

## 2. Introduction & Background

### 2.1 Current State

Across Gujarat State, multiple departments have deployed CCTV cameras independently:

| Department | Camera Count | Current System | Gap |
|------------|--------------|----------------|-----|
| Home Department | 3,500 | Multiple VMS | No unified view |
| Transport (RTO) | 2,000 | Department-specific | Fragmented |
| Food & Civil Supplies | 1,500 | Limited tracking | No central registry |
| Urban Development | 1,200 | City-specific | No state-wide view |
| Revenue | 800 | Local systems | No inventory |
| Health | 600 | Hospital-specific | No central tracking |
| Others (20 depts) | 3,400 | Various | No unified system |
| **Total** | **13,000** | **Fragmented** | **No central mechanism** |

### 2.2 Problem Statement

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT PROBLEMS                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. NO CENTRALISED INVENTORY                                                 │
│     - 26 departments, no unified camera registry                            │
│     - Duplicate entries, missing records                                    │
│     - Incomplete metadata                                                   │
│                                                                              │
│  2. NO GIS VISUALIZATION                                                     │
│     - Cannot see cameras on map                                             │
│     - No coverage visualization                                             │
│     - Difficult to identify gaps                                            │
│                                                                              │
│  3. NO STATUS TRACKING                                                       │
│     - Unknown if cameras are working                                        │
│     - No maintenance scheduling                                             │
│     - No health monitoring                                                  │
│                                                                              │
│  4. NO GAP ANALYSIS                                                          │
│     - Cannot identify uncovered areas                                       │
│     - Cannot assess infrastructure age                                      │
│     - Cannot plan future deployment                                         │
│                                                                              │
│  5. NO INTEGRATION FOUNDATION                                                │
│     - No base for Model 2, 3, 4                                             │
│     - Cannot plan unified viewing                                           │
│     - Cannot plan analytics integration                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Solution Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 1 SOLUTION OVERVIEW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OBJECTIVE: Create unified inventory and visibility layer                    │
│                                                                              │
│  APPROACH:                                                                   │
│  ├── Centralised Registry (Metadata Management)                             │
│  ├── GIS Mapping (Visual Representation)                                    │
│  ├── Health Monitoring (Status Tracking)                                    │
│  ├── Gap Analysis (Coverage Planning)                                       │
│  └── APIs (Integration Foundation)                                          │
│                                                                              │
│  SCOPE:                                                                      │
│  ✓ Camera metadata onboarding                                               │
│  ✓ GIS-based visualization                                                  │
│  ✓ Status monitoring                                                        │
│  ✓ Gap analysis reports                                                     │
│  ✗ NO live video streaming                                                  │
│  ✗ NO centralised recording                                                 │
│  ✗ NO analytics processing                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Camera Onboarding

#### 3.1.1 Bulk Import

| Feature | Description | Priority |
|---------|-------------|----------|
| CSV/Excel Upload | Import camera data from spreadsheet | Mandatory |
| Template Download | Pre-defined template for data entry | Mandatory |
| Validation Rules | Auto-validate data format, required fields | Mandatory |
| Error Handling | Report errors, allow correction | Mandatory |
| Progress Tracking | Show upload progress | Mandatory |
| Duplicate Detection | Identify and flag duplicates | Mandatory |

**Bulk Import Template:**

| Field | Type | Required | Example |
|-------|------|----------|---------|
| Camera ID | String | Yes | CAM-AHM-001 |
| Department | String | Yes | Home Department |
| Location Name | String | Yes | SG Highway Junction |
| Latitude | Decimal | Yes | 23.0225 |
| Longitude | Decimal | Yes | 72.5714 |
| Address | String | Yes | Near Science City, Ahmedabad |
| District | String | Yes | Ahmedabad |
| Camera Make | String | Yes | Hikvision |
| Camera Model | String | Yes | DS-2CD2T47G2 |
| Camera Type | Enum | Yes | Fixed/PTZ/Dome/Bullet |
| Resolution | Enum | Yes | 1080p/4K/2K |
| IP Address | String | No | 192.168.1.100 |
| Protocol | Enum | Yes | ONVIF/RTSP/Analog |
| Connectivity | Enum | Yes | Wired/Wireless/4G |
| Storage Type | Enum | Yes | Cloud/Local/Hybrid |
| Storage Location | String | No | AWS S3 / Local NVR |
| Retention Days | Integer | Yes | 15 |
| Installation Date | Date | Yes | 2024-01-15 |
| Warranty Expiry | Date | No | 2027-01-15 |
| AMC Status | Enum | Yes | Active/Expired/Never |
| Contact Person | String | Yes | Ramesh Patel |
| Contact Phone | String | Yes | +91-98765-43210 |
| Status | Enum | Yes | Active/Inactive/Maintenance |

#### 3.1.2 Manual Entry

| Feature | Description | Priority |
|---------|-------------|----------|
| Web Form | Single camera entry form | Mandatory |
| Field Validation | Real-time validation | Mandatory |
| Auto-save | Draft saving | Mandatory |
| Photo Upload | Camera installation photo | Mandatory |
| Map Selection | Click on map for coordinates | Mandatory |
| Quick Copy | Clone existing camera entry | Desirable |

#### 3.1.3 API-Based Onboarding

| Feature | Description | Priority |
|---------|-------------|----------|
| REST API | CRUD operations for cameras | Mandatory |
| Webhook | Real-time status updates | Mandatory |
| Authentication | API key + OAuth 2.0 | Mandatory |
| Rate Limiting | Prevent abuse | Mandatory |
| Versioning | API version management | Mandatory |
| Documentation | OpenAPI/Swagger spec | Mandatory |

**API Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/cameras | List all cameras |
| POST | /api/v1/cameras | Create camera |
| GET | /api/v1/cameras/{id} | Get camera details |
| PUT | /api/v1/cameras/{id} | Update camera |
| DELETE | /api/v1/cameras/{id} | Delete camera |
| POST | /api/v1/cameras/bulk | Bulk import |
| GET | /api/v1/cameras/search | Search cameras |
| GET | /api/v1/cameras/health | Get health status |
| GET | /api/v1/cameras/gap-analysis | Get gap analysis |

---

### 3.2 GIS Mapping

#### 3.2.1 Map Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Interactive Map | Pan, zoom, click | Mandatory |
| Multiple Layers | Toggle layers on/off | Mandatory |
| Cluster View | Cluster nearby cameras | Mandatory |
| Satellite View | Satellite imagery | Mandatory |
| Street View | Street-level view | Mandatory |
| 3D View | 3D visualization | Desirable |
| Heat Map | Density visualization | Desirable |
| Drawing Tools | Draw zones, lines | Mandatory |
| Measurement Tool | Distance/area measurement | Desirable |
| Screenshot | Export map view | Mandatory |

#### 3.2.2 Map Layers

| Layer | Description | Color Code |
|-------|-------------|------------|
| Department Layer | Cameras by department | Color per department |
| Status Layer | Active/Inactive/Maintenance | Green/Red/Yellow |
| Type Layer | Fixed/PTZ/Dome/Bullet | Different icons |
| Connectivity Layer | Wired/Wireless/4G | Different styles |
| Storage Layer | Cloud/Local/Hybrid | Different patterns |
| Age Layer | Camera age (1yr, 2yr, 3yr+) | Gradient colors |
| Coverage Layer | Coverage circles | Semi-transparent |
| Gap Layer | Uncovered zones | Red zones |
| Heat Layer | Camera density | Heat gradient |

#### 3.2.3 Map Interactions

| Interaction | Description | Priority |
|-------------|-------------|----------|
| Click on Camera | Show camera details popup | Mandatory |
| Hover | Show quick info tooltip | Mandatory |
| Select Multiple | Multi-select for bulk actions | Mandatory |
| Filter on Map | Apply filters to map view | Mandatory |
| Export View | Export current map view | Mandatory |
| Share View | Share map view URL | Desirable |
| Print Map | Print current view | Mandatory |

---

### 3.3 Camera Health Monitoring

#### 3.3.1 Health Parameters

| Parameter | Description | Update Frequency |
|-----------|-------------|------------------|
| Online/Offline | Connectivity status | Real-time |
| Last Seen | Last time camera was online | Real-time |
| Stream Quality | Video quality status | Every 5 min |
| Storage Status | Storage availability | Every 1 hour |
| Firmware Version | Current firmware | Daily |
| CPU Usage | Processing load | Every 5 min |
| Temperature | Device temperature | Every 5 min |
| Network Latency | Connection latency | Every 5 min |
| Disk Space | Available storage | Every 1 hour |
| Motion Detection | Motion sensor status | Real-time |

#### 3.3.2 Health Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HEALTH DASHBOARD                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SUMMARY CARDS                                                       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ Total   │ │ Online  │ │ Offline │ │ Maint.  │ │ Unknown │     │   │
│  │  │ 13,000  │ │ 11,500  │ │ 1,200   │ │ 200     │ │ 100     │     │   │
│  │  │ (100%)  │ │ (88%)   │ │ (9%)    │ │ (2%)    │ │ (1%)    │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DEPARTMENT-WISE STATUS                                              │   │
│  │                                                                      │   │
│  │  Home Dept      ████████████████████░░░░  85% Online               │   │
│  │  RTO            ██████████████████████░░  92% Online               │   │
│  │  Food & Civil   ████████████████░░░░░░░░  78% Online               │   │
│  │  Urban Dev      ████████████████████████  98% Online               │   │
│  │  Revenue        ██████████████████░░░░░░  88% Online               │   │
│  │  Health         ████████████████████░░░░  85% Online               │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ALERTS & NOTIFICATIONS                                              │   │
│  │                                                                      │   │
│  │  🔴 CRITICAL: 15 cameras offline for 24+ hours                     │   │
│  │  🟡 WARNING: 50 cameras with low storage                           │   │
│  │  🟢 INFO: 25 cameras firmware update available                     │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.3 Alert Rules

| Alert Type | Condition | Notification |
|------------|-----------|--------------|
| Camera Offline | Offline > 1 hour | Email + SMS |
| Camera Critical | Offline > 24 hours | Email + SMS + Dashboard |
| Low Storage | Storage < 20% | Email |
| Storage Full | Storage < 5% | Email + SMS |
| High Temperature | Temperature > 70°C | Email |
| High Latency | Latency > 500ms | Email |
| Firmware Update | New version available | Email |
| Warranty Expiring | Expiry < 30 days | Email |

---

### 3.4 Gap Analysis

#### 3.4.1 Gap Analysis Parameters

| Parameter | Description | Calculation |
|-----------|-------------|-------------|
| Coverage Gap | Areas without cameras | GIS overlay analysis |
| Density Gap | Areas with low camera density | Cameras per sq km |
| Redundancy | Overlapping camera coverage | Coverage overlap % |
| Age Gap | Old cameras needing replacement | Installation date |
| Technology Gap | Analog vs IP cameras | Technology distribution |
| Storage Gap | Insufficient storage capacity | Storage vs retention |
| Connectivity Gap | Poor network connectivity | Bandwidth analysis |
| Maintenance Gap | Overdue maintenance | AMC status |

#### 3.4.2 Gap Analysis Reports

**Report 1: Coverage Analysis**

| District | Area (sq km) | Cameras | Density (per sq km) | Status |
|----------|--------------|---------|---------------------|--------|
| Ahmedabad | 505 | 1,580 | 3.13 | Good |
| Surat | 4,327 | 1,270 | 0.29 | Low |
| Vadodara | 7,555 | 1,070 | 0.14 | Critical |
| Rajkot | 11,203 | 850 | 0.08 | Critical |
| Others | 1,70,000 | 8,230 | 0.05 | Critical |

**Report 2: Technology Gap**

| Technology | Count | Percentage | Replacement Needed |
|------------|-------|------------|-------------------|
| IP (H.265) | 5,000 | 38% | None |
| IP (H.264) | 4,500 | 35% | Upgrade to H.265 |
| Analog | 2,500 | 19% | Replace with IP |
| Mixed | 1,000 | 8% | Standardize |

**Report 3: Age Analysis**

| Age Group | Count | Percentage | Action |
|-----------|-------|------------|--------|
| 0-1 years | 2,000 | 15% | Maintain |
| 1-2 years | 3,500 | 27% | Monitor |
| 2-3 years | 4,000 | 31% | Plan upgrade |
| 3-5 years | 2,500 | 19% | Replace |
| 5+ years | 1,000 | 8% | Immediate replace |

---

### 3.5 Search & Filter

#### 3.5.1 Search Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Text Search | Search by camera ID, location | Mandatory |
| Advanced Search | Multi-field search | Mandatory |
| Saved Searches | Save frequently used searches | Mandatory |
| Search History | Recent searches | Desirable |
| Autocomplete | Search suggestions | Desirable |
| Fuzzy Search | Approximate matching | Desirable |

#### 3.5.2 Filter Options

| Filter | Options |
|--------|---------|
| Department | All departments dropdown |
| District | All 33 districts |
| Camera Type | Fixed, PTZ, Dome, Bullet |
| Status | Active, Inactive, Maintenance |
| Connectivity | Wired, Wireless, 4G |
| Storage | Cloud, Local, Hybrid |
| Age | 0-1yr, 1-2yr, 2-3yr, 3-5yr, 5+yr |
| Technology | IP (H.265), IP (H.264), Analog |
| Resolution | 1080p, 2K, 4K |
| Make/Brand | Hikvision, Dahua, Axis, etc. |

---

### 3.6 Role-Based Access Control

#### 3.6.1 User Roles

| Role | Access Level | Permissions |
|------|--------------|-------------|
| Super Admin | Full system | All operations |
| State Admin | State-wide | All departments |
| District Admin | District-level | District cameras |
| Department Head | Department-level | Department cameras |
| Operator | Limited | View, search |
| Auditor | Read-only | Reports, audit logs |

#### 3.6.2 Permission Matrix

| Permission | Super Admin | State Admin | District Admin | Dept Head | Operator | Auditor |
|------------|-------------|-------------|----------------|-----------|----------|---------|
| View Cameras | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Add Camera | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Edit Camera | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Delete Camera | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| View Reports | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Export Data | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Manage Users | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| View Audit Logs | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Bulk Import | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

---

### 3.7 Audit Trail

#### 3.7.1 Audit Log Fields

| Field | Description |
|-------|-------------|
| Timestamp | Date and time of action |
| User ID | User who performed action |
| User Name | User's display name |
| Action | Action performed |
| Module | System module affected |
| Record ID | Affected record ID |
| Old Value | Previous value |
| New Value | New value |
| IP Address | User's IP address |
| Device Info | Browser/device details |

#### 3.7.2 Tracked Actions

| Module | Actions Tracked |
|--------|-----------------|
| Camera | Create, Update, Delete, View |
| User | Create, Update, Delete, Login, Logout |
| Report | Generate, Export, View |
| Settings | Update |
| Import | Start, Complete, Fail |

---

## 4. Technical Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 1 SYSTEM ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PRESENTATION LAYER                                │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  React.js    │  │  Map Engine  │  │  Dashboard   │              │   │
│  │  │  Web App     │  │  Leaflet/    │  │  Charts &    │              │   │
│  │  │              │  │  OpenLayers  │  │  Reports     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    API GATEWAY LAYER                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Nginx / Kong API Gateway                                    │   │   │
│  │  │  - Rate Limiting  - Authentication  - Load Balancing         │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    APPLICATION LAYER                                 │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Camera      │  │  Registry    │  │  Gap         │              │   │
│  │  │  Service     │  │  Service     │  │  Analysis    │              │   │
│  │  │              │  │              │  │  Service     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Health      │  │  Search      │  │  Audit       │              │   │
│  │  │  Monitor     │  │  Service     │  │  Service     │              │   │
│  │  │  Service     │  │              │  │              │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DATA LAYER                                        │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  PostgreSQL  │  │  PostGIS     │  │  Redis       │              │   │
│  │  │  + PostGIS   │  │  Extension   │  │  Cache       │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  File Storage│  │  Elasticsearch│  │  InfluxDB   │              │   │
│  │  │  (MinIO)     │  │  (Search)    │  │  (Metrics)  │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Database Schema

#### 4.2.1 Core Tables

```sql
-- Camera Registry Table
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id VARCHAR(50) UNIQUE NOT NULL,
    department_id UUID NOT NULL,
    location_name VARCHAR(200) NOT NULL,
    address TEXT,
    district_id UUID NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    camera_make VARCHAR(100),
    camera_model VARCHAR(100),
    camera_type VARCHAR(20) NOT NULL,
    resolution VARCHAR(20),
    ip_address VARCHAR(45),
    protocol VARCHAR(20),
    connectivity VARCHAR(20),
    storage_type VARCHAR(20),
    storage_location VARCHAR(200),
    retention_days INTEGER,
    installation_date DATE,
    warranty_expiry DATE,
    amc_status VARCHAR(20),
    contact_person VARCHAR(100),
    contact_phone VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Department Table
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    nodal_officer VARCHAR(200),
    contact_email VARCHAR(200),
    contact_phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- District Table
CREATE TABLE districts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    region VARCHAR(100),
    area_sq_km DECIMAL(10, 2),
    geom GEOMETRY(MultiPolygon, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Camera Health Status Table
CREATE TABLE camera_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES cameras(id),
    status VARCHAR(20) NOT NULL,
    last_seen TIMESTAMP,
    stream_quality VARCHAR(20),
    storage_status VARCHAR(20),
    firmware_version VARCHAR(50),
    cpu_usage DECIMAL(5, 2),
    temperature DECIMAL(5, 2),
    network_latency INTEGER,
    disk_space_available BIGINT,
    checked_at TIMESTAMP DEFAULT NOW()
);

-- Audit Log Table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    user_name VARCHAR(200),
    action VARCHAR(50) NOT NULL,
    module VARCHAR(50) NOT NULL,
    record_id UUID,
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(45),
    device_info TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 4.2.2 Spatial Index

```sql
-- Spatial Index for GIS queries
CREATE INDEX idx_cameras_geom ON cameras USING GIST(geom);
CREATE INDEX idx_districts_geom ON districts USING GIST(geom);

-- Other indexes
CREATE INDEX idx_cameras_department ON cameras(department_id);
CREATE INDEX idx_cameras_district ON cameras(district_id);
CREATE INDEX idx_cameras_status ON cameras(status);
CREATE INDEX idx_camera_health_camera ON camera_health(camera_id);
CREATE INDEX idx_camera_health_status ON camera_health(status);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

### 4.3 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Frontend** | | | |
| UI Framework | React.js | 18.x | Web application |
| Map Library | Leaflet | 1.9.x | GIS mapping |
| UI Components | Ant Design | 5.x | UI elements |
| Charts | Chart.js / D3.js | Latest | Visualizations |
| State Management | Redux | 4.x | State handling |
| **Backend** | | | |
| Runtime | Node.js | 20 LTS | Server runtime |
| Framework | Express.js | 4.x | API framework |
| ORM | Prisma | 5.x | Database ORM |
| Validation | Joi / Zod | Latest | Input validation |
| **Database** | | | |
| Primary | PostgreSQL | 16 | Data storage |
| GIS Extension | PostGIS | 3.4 | Spatial queries |
| Cache | Redis | 7.x | Caching |
| Search | Elasticsearch | 8.x | Full-text search |
| Time Series | InfluxDB | 2.x | Health metrics |
| **Storage** | | | |
| Object Storage | MinIO | Latest | File storage |
| **DevOps** | | | |
| Container | Docker | Latest | Containerization |
| Orchestration | Kubernetes | 1.28+ | Deployment |
| CI/CD | GitLab CI | - | Pipeline |
| Monitoring | Prometheus + Grafana | Latest | Monitoring |

---

## 5. User Interface Design

### 5.1 Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  HEADER: Logo | Search | Notifications | User Profile | Logout       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────┐ ┌────────────────────────────────────────────────────────┐ │
│  │            │ │                                                          │ │
│  │  SIDEBAR   │ │  MAIN CONTENT AREA                                      │ │
│  │            │ │                                                          │ │
│  │  - Dashboard│ │  ┌─────────────────────────────────────────────────┐  │ │
│  │  - Map View │ │  │  GIS MAP VIEW                                    │  │ │
│  │  - Cameras  │ │  │                                                   │  │ │
│  │  - Reports  │ │  │     [Interactive Map with Camera Markers]        │  │ │
│  │  - Health   │ │  │                                                   │  │ │
│  │  - Settings │ │  │                                                   │  │ │
│  │  - Users    │ │  └─────────────────────────────────────────────────┘  │ │
│  │  - Audit    │ │                                                          │ │
│  │            │ │  ┌─────────────────────────────────────────────────┐  │ │
│  │            │ │  │  SUMMARY CARDS                                   │  │ │
│  │            │ │  │  [Total] [Online] [Offline] [Departments]       │  │ │
│  │            │ │  └─────────────────────────────────────────────────┘  │ │
│  │            │ │                                                          │ │
│  └────────────┘ └────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Map View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MAP VIEW                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MAP CONTROLS                                                       │   │
│  │  [Zoom +/-] [Satellite/Street] [Layers] [Filters] [Export] [Print] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │                    ┌──────────────────────┐                         │   │
│  │                    │    Ahmedabad          │                         │   │
│  │                    │    ●●●●●●●●           │                         │   │
│  │                    │    ●●●●●●●●           │                         │   │
│  │                    │    ●●●●●●●●           │                         │   │
│  │                    │         Rajkot ●●●●●  │                         │   │
│  │                    │              ●●●●●     │                         │   │
│  │                    │                    ●●● │                         │   │
│  │                    │              Surat ●●● │                         │   │
│  │                    │               ●●●●     │                         │   │
│  │                    └──────────────────────┘                         │   │
│  │                                                                      │   │
│  │  Legend: ● Active  ● Inactive  ● Maintenance  ○ Gap Zone           │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LAYER PANEL (Toggle)                                               │   │
│  │  ☑ Department    ☑ Status    ☐ Type    ☐ Connectivity              │   │
│  │  ☐ Storage       ☐ Age       ☐ Coverage ☐ Gap                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Camera Details View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CAMERA DETAILS - CAM-AHM-001                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  BASIC INFORMATION                                                   │   │
│  │  ┌─────────────────────────┬─────────────────────────────────────┐ │   │
│  │  │ Camera ID:              │ CAM-AHM-001                         │ │   │
│  │  │ Department:             │ Home Department                     │ │   │
│  │  │ Location:               │ SG Highway Junction                 │ │   │
│  │  │ District:               │ Ahmedabad                           │ │   │
│  │  │ Coordinates:            │ 23.0225, 72.5714                    │ │   │
│  │  │ Status:                 │ 🟢 Active                           │ │   │
│  │  └─────────────────────────┴─────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TECHNICAL DETAILS                                                   │   │
│  │  ┌─────────────────────────┬─────────────────────────────────────┐ │   │
│  │  │ Make/Model:             │ Hikvision DS-2CD2T47G2              │ │   │
│  │  │ Type:                   │ Bullet                              │ │   │
│  │  │ Resolution:             │ 4MP (2K)                            │ │   │
│  │  │ Protocol:               │ ONVIF                               │ │   │
│  │  │ IP Address:             │ 192.168.1.100                       │ │   │
│  │  │ Connectivity:           │ Wired                               │ │   │
│  │  └─────────────────────────┴─────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  HEALTH STATUS (Real-time)                                           │   │
│  │  ┌─────────────────────────┬─────────────────────────────────────┐ │   │
│  │  │ Online Status:          │ 🟢 Online                           │ │   │
│  │  │ Last Seen:              │ 2 minutes ago                       │ │   │
│  │  │ Stream Quality:         │ Good (4MP)                          │ │   │
│  │  │ Storage:                │ 75% Available                       │ │   │
│  │  │ Network Latency:        │ 15ms                                │ │   │
│  │  │ Temperature:            │ 42°C                                │ │   │
│  │  └─────────────────────────┴─────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  [Edit] [Delete] [Export] [View on Map] [Health History]            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. API Documentation

### 6.1 Camera APIs

#### 6.1.1 List Cameras

```
GET /api/v1/cameras

Query Parameters:
- page (default: 1)
- limit (default: 20, max: 100)
- department_id
- district_id
- status
- camera_type
- search

Response:
{
  "success": true,
  "data": {
    "cameras": [...],
    "pagination": {
      "total": 13000,
      "page": 1,
      "limit": 20,
      "pages": 650
    }
  }
}
```

#### 6.1.2 Create Camera

```
POST /api/v1/cameras

Request Body:
{
  "camera_id": "CAM-AHM-001",
  "department_id": "uuid",
  "location_name": "SG Highway Junction",
  "latitude": 23.0225,
  "longitude": 72.5714,
  "camera_make": "Hikvision",
  "camera_model": "DS-2CD2T47G2",
  "camera_type": "bullet",
  "resolution": "2k",
  "protocol": "onvif",
  "status": "active"
}

Response:
{
  "success": true,
  "data": {
    "id": "uuid",
    "camera_id": "CAM-AHM-001",
    "created_at": "2026-09-15T10:00:00Z"
  }
}
```

#### 6.1.3 Bulk Import

```
POST /api/v1/cameras/bulk

Request: multipart/form-data
- file: CSV/Excel file

Response:
{
  "success": true,
  "data": {
    "import_id": "uuid",
    "total_rows": 1000,
    "successful": 980,
    "failed": 20,
    "errors": [...]
  }
}
```

#### 6.1.4 Get Camera Health

```
GET /api/v1/cameras/{id}/health

Response:
{
  "success": true,
  "data": {
    "camera_id": "uuid",
    "status": "online",
    "last_seen": "2026-09-15T10:05:00Z",
    "stream_quality": "good",
    "storage_status": "75% available",
    "network_latency": 15,
    "temperature": 42
  }
}
```

### 6.2 GIS APIs

#### 6.2.1 Get Cameras by Bounds

```
GET /api/v1/gis/cameras/bounds

Query Parameters:
- north (latitude)
- south (latitude)
- east (longitude)
- west (longitude)
- department_id (optional)
- status (optional)

Response:
{
  "success": true,
  "data": {
    "cameras": [
      {
        "id": "uuid",
        "camera_id": "CAM-AHM-001",
        "lat": 23.0225,
        "lng": 72.5714,
        "status": "online",
        "department": "Home Department"
      }
    ],
    "total": 500
  }
}
```

#### 6.2.2 Get Coverage Analysis

```
GET /api/v1/gis/coverage

Query Parameters:
- district_id (optional)
- department_id (optional)
- radius_km (default: 1)

Response:
{
  "success": true,
  "data": {
    "total_area_sq_km": 505,
    "covered_area_sq_km": 350,
    "coverage_percentage": 69.3,
    "gaps": [
      {
        "location": "Area Name",
        "lat": 23.0300,
        "lng": 72.5800,
        "nearest_camera_distance_km": 2.5
      }
    ]
  }
}
```

### 6.3 Report APIs

#### 6.3.1 Generate Gap Analysis Report

```
POST /api/v1/reports/gap-analysis

Request Body:
{
  "district_id": "uuid",
  "department_id": "uuid",
  "analysis_type": "coverage|density|age|technology"
}

Response:
{
  "success": true,
  "data": {
    "report_id": "uuid",
    "generated_at": "2026-09-15T10:00:00Z",
    "summary": {...},
    "details": [...],
    "download_url": "/api/v1/reports/gap-analysis/uuid/download"
  }
}
```

---

## 7. Deliverables

### 7.1 Deliverables Checklist

| # | Deliverable | Description | Acceptance Criteria |
|---|-------------|-------------|---------------------|
| 1 | **Working Registry Portal** | Complete web application | All features functional |
| 2 | **GIS Map View** | Interactive map with all layers | All layers working |
| 3 | **Bulk Import** | CSV/Excel upload functionality | 10,000+ records import |
| 4 | **Manual Entry** | Single camera entry form | All fields validated |
| 5 | **API Documentation** | Complete API docs | OpenAPI/Swagger spec |
| 6 | **Sample Dataset** | 1,000 sample cameras | All fields populated |
| 7 | **Gap Analysis Report** | Sample report | All analysis types |
| 8 | **Health Dashboard** | Real-time status view | Live status updates |
| 9 | **User Manual** | End-user documentation | Complete user guide |
| 10 | **Admin Guide** | System administration guide | Complete admin guide |

### 7.2 Sample Dataset Structure

| Field | Sample Value |
|-------|--------------|
| Camera ID | CAM-AHM-001 |
| Department | Home Department |
| Location | SG Highway Junction, Ahmedabad |
| Latitude | 23.02250000 |
| Longitude | 72.57140000 |
| Make/Model | Hikvision DS-2CD2T47G2 |
| Type | Bullet |
| Resolution | 2K |
| Protocol | ONVIF |
| IP Address | 192.168.1.100 |
| Connectivity | Wired |
| Storage | Cloud (AWS S3) |
| Retention | 15 days |
| Installation | 2024-01-15 |
| Status | Active |

---

## 8. Integration Points

### 8.1 Integration with Other Models

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL 1 INTEGRATION POINTS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MODEL 1: REGISTRY & GIS                           │   │
│  │                    (Current Model)                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│            ┌───────────────────────┼───────────────────────┐              │
│            │                       │                       │              │
│            ▼                       ▼                       ▼              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│  │   MODEL 2       │    │   MODEL 3       │    │   MODEL 4       │       │
│  │   Unified       │    │   Middleware    │    │   Central VMS   │       │
│  │   Viewing       │    │   Federation   │    │   Full System   │       │
│  │                 │    │                 │    │                 │       │
│  │ Uses: Camera    │    │ Uses: Camera    │    │ Uses: Camera    │       │
│  │ metadata from   │    │ metadata from   │    │ metadata from   │       │
│  │ Model 1         │    │ Model 1         │    │ Model 1         │       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘       │
│                                                                              │
│  INTEGRATION TYPE: Model 1 provides camera registry data to all models     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 External System Integrations

| System | Integration Type | Data Flow |
|--------|------------------|-----------|
| Department VMS | API polling | Status updates |
| Network Monitoring | SNMP traps | Health data |
| Asset Management | REST API | Hardware info |
| HR System | REST API | User data |
| Email System | SMTP | Notifications |
| SMS Gateway | REST API | SMS alerts |

---

## 9. Implementation Plan

### 9.1 Phase-wise Implementation

| Phase | Duration | Activities |
|-------|----------|------------|
| **Phase 1: Foundation** | Month 1-2 | Database setup, core APIs, basic UI |
| **Phase 2: GIS** | Month 3-4 | Map integration, layers, spatial queries |
| **Phase 3: Onboarding** | Month 5-6 | Bulk import, manual entry, API onboarding |
| **Phase 4: Health** | Month 7-8 | Health monitoring, alerts, dashboards |
| **Phase 5: Reports** | Month 9-10 | Gap analysis, reports, analytics |
| **Phase 6: Testing** | Month 11-12 | UAT, performance, security testing |
| **Phase 7: Deployment** | Month 13 | Production deployment, training |

### 9.2 Resource Requirements

| Role | Count | Duration |
|------|-------|----------|
| Project Manager | 1 | 13 months |
| Solution Architect | 1 | 13 months |
| Backend Developer | 3 | 12 months |
| Frontend Developer | 2 | 12 months |
| GIS Specialist | 1 | 10 months |
| Database Administrator | 1 | 13 months |
| QA Engineer | 2 | 10 months |
| DevOps Engineer | 1 | 13 months |

---

## 10. Testing Strategy

### 10.1 Test Cases

| Category | Test Case | Expected Result |
|----------|-----------|-----------------|
| **Functional** | | |
| Camera CRUD | Create, Read, Update, Delete camera | All operations work |
| Bulk Import | Import 10,000 records | 100% success |
| GIS Map | Display cameras on map | All markers visible |
| Search | Search by multiple criteria | Accurate results |
| Filter | Apply multiple filters | Correct filtering |
| Reports | Generate gap analysis | Report generated |
| **Performance** | | |
| Load Test | 1,000 concurrent users | No degradation |
| API Response | All API calls | < 200ms |
| Map Rendering | Display 10,000 markers | < 3 seconds |
| **Security** | | |
| Authentication | Unauthorized access | Blocked |
| Authorization | Role-based access | Enforced |
| Data Encryption | Data at rest/in transit | Encrypted |

---

## 11. Success Metrics

| Metric | Target |
|--------|--------|
| Camera Registry | 100% cameras onboarded |
| Data Accuracy | 99%+ metadata accuracy |
| GIS Coverage | All 33 districts covered |
| System Uptime | 99.9% |
| User Adoption | 100% departments using |
| Gap Analysis | Monthly reports generated |

---

## 12. Appendix

### 12.1 Glossary

| Term | Definition |
|------|------------|
| GIS | Geographic Information System |
| PostGIS | PostgreSQL spatial extension |
| ONVIF | Open Network Video Interface Forum |
| RTSP | Real Time Streaming Protocol |
| VMS | Video Management System |
| CRUD | Create, Read, Update, Delete |
| API | Application Programming Interface |

### 12.2 Reference Documents

1. Gujarat State CCTV Integration Project - Project Background
2. Detailed Technical Design Document
3. Department-wise Integration Plan
4. Vendor Evaluation Criteria

---

*Document Version: 1.0*
*Prepared for: Gujarat State CCTV Integration Project*
*Date: September 2026*
*Classification: Confidential*
*Model: 1 - Centralised CCTV Registry & GIS-Based Mapping Platform*