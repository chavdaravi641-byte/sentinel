# Gujarat State CCTV Integration Project
## Combined Models Integration Architecture

---

## Document Control

| Parameter | Details |
|-----------|---------|
| Document Title | Combined Models Integration Architecture |
| Version | 1.0 |
| Date | September 2026 |
| Classification | Confidential |
| Purpose | How Models 1-4 work together |

---

## 1. Executive Summary

This document describes how the four proposed models integrate to create a comprehensive CCTV solution for Gujarat State. The models are designed to work independently or in combination, providing flexibility in implementation approach.

**Key Insight:** Model 1 (Registry & GIS) is the **foundational model** that must be combined with one or more of Models 2, 3, or 4 to enable full functionality.

---

## 2. Model Overview

### 2.1 Model Comparison

| Feature | Model 1 | Model 2 | Model 3 | Model 4 |
|---------|---------|---------|---------|---------|
| **Primary Focus** | Registry & GIS | Unified Viewing | Middleware/Federation | Full Central VMS |
| **Live Streaming** | ✗ | ✓ | ✓ | ✓ |
| **Central Storage** | ✗ | ✗ | ✗ | ✓ |
| **Analytics** | ✗ | Limited (ANPR) | Limited | Full (AI/ML) |
| **Database Integration** | ✗ | Partial | Partial | Full |
| **GIS Mapping** | ✓ | ✗ | ✗ | ✗ |
| **Gap Analysis** | ✓ | ✗ | ✗ | ✗ |
| **VMS Replacement** | No | No | No | Yes |
| **Infrastructure** | Minimal | Medium | Medium | Heavy |
| **Cost** | Low | Medium | Medium | High |
| **Complexity** | Low | Medium | Medium | High |

### 2.2 Model Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL DEPENDENCIES                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MODEL 1: REGISTRY & GIS                           │   │
│  │                    (Foundational - Required)                         │   │
│  │                                                                      │   │
│  │  Provides: Camera metadata, location data, status information      │   │
│  │  Used by: All other models                                         │   │
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
│  │  Can work with  │    │  Can work with  │    │  Can work with  │       │
│  │  Model 1 only   │    │  Model 1 only   │    │  Model 1 only   │       │
│  │  OR             │    │  OR             │    │  OR             │       │
│  │  Model 1 + 3    │    │  Model 1 + 2    │    │  Model 1 + 2 + 3│      │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Integration Architecture

### 3.1 Full Integration (All Models Combined)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FULL INTEGRATION ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MODEL 1: REGISTRY & GIS                                             │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - Camera metadata database                                  │   │   │
│  │  │  - GIS mapping platform                                      │   │   │
│  │  │  - Health monitoring                                         │   │   │
│  │  │  - Gap analysis                                              │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Provides to other models:                                          │   │
│  │  - Camera location data                                            │   │
│  │  - Camera status information                                       │   │
│  │  - Department metadata                                             │   │
│  │  - District/region data                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MODEL 3: MIDDLEWARE/FEDERATION                                      │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - VMS adapters (Milestone, Genetec, etc.)                  │   │   │
│  │  │  - Metadata exchange bus                                     │   │   │
│  │  │  - Event correlation engine                                  │   │   │
│  │  │  - Unified workflow                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Provides to Model 4:                                               │   │
│  │  - Federated camera access                                         │   │
│  │  - Cross-system events                                             │   │
│  │  - VMS-specific data                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MODEL 2: UNIFIED VIEWING                                            │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - Live feed aggregation                                     │   │   │
│  │  │  - ANPR metadata generation                                  │   │   │
│  │  │  - Video wall configuration                                  │   │   │
│  │  │  - Searchable records                                        │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Uses from Model 1: Camera metadata, locations                      │   │
│  │  Uses from Model 3: Federated streams, events                      │   │
│  │  Provides to Model 4: Viewing interface, ANPR data                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MODEL 4: CENTRAL VMS                                                │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  - Centralized recording & storage                           │   │   │
│  │  │  - Advanced AI analytics                                     │   │   │
│  │  │  - Database integration (VAHAN, SARTHI, eGujCop, AFIS)      │   │   │
│  │  │  - Vehicle tracking & route reconstruction                   │   │   │
│  │  │  - Disaster recovery                                         │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Uses from Model 1: Camera registry, locations                      │   │
│  │  Uses from Model 3: Federated access to existing VMS               │   │
│  │  Uses from Model 2: Viewing interface, ANPR data                   │   │
│  │                                                                      │   │
│  │  Provides:                                                          │   │
│  │  - Centralized storage for all feeds                               │   │
│  │  - Advanced analytics                                              │   │
│  │  - Database integration                                            │   │
│  │  - Vehicle tracking                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow Between Models

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA FLOW BETWEEN MODELS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MODEL 1 (Registry)                                                         │
│  │                                                                           │
│  │  Provides:                                                               │
│  │  ├── Camera metadata (ID, location, department)                        │
│  │  ├── Camera status (online/offline)                                     │
│  │  ├── District/region data                                               │
│  │  └── GIS coordinates                                                    │
│  │                                                                           │
│  ▼                                                                           │
│  MODEL 3 (Middleware)                                                       │
│  │                                                                           │
│  │  Provides:                                                               │
│  │  ├── Federated camera access (via adapters)                            │
│  │  ├── Cross-system events                                                │
│  │  ├── VMS-specific metadata                                             │
│  │  └── Unified event stream                                               │
│  │                                                                           │
│  ▼                                                                           │
│  MODEL 2 (Viewing)                                                          │
│  │                                                                           │
│  │  Provides:                                                               │
│  │  ├── Live video streams                                                 │
│  │  ├── ANPR metadata                                                      │
│  │  ├── Video wall views                                                   │
│  │  └── Searchable records                                                 │
│  │                                                                           │
│  ▼                                                                           │
│  MODEL 4 (Central VMS)                                                     │
│  │                                                                           │
│  │  Uses from all models:                                                   │
│  │  ├── Camera metadata (Model 1)                                          │
│  │  ├── Federated access (Model 3)                                         │
│  │  ├── Viewing interface (Model 2)                                        │
│  │  │                                                                       │
│  │  Provides:                                                               │
│  │  ├── Centralized storage                                                │
│  │  ├── Advanced analytics (ANPR, Face, Vehicle)                          │
│  │  ├── Database integration (VAHAN, SARTHI, eGujCop, AFIS)              │
│  │  ├── Vehicle tracking                                                   │
│  │  └── Disaster recovery                                                  │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Approaches

### 4.1 Approach A: Phased Implementation (Recommended)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    APPROACH A: PHASED IMPLEMENTATION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1 (Month 1-12): FOUNDATION                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Implement: Model 1 (Registry & GIS)                               │   │
│  │                                                                      │   │
│  │  Deliverables:                                                      │   │
│  │  - Camera registry portal                                          │   │
│  │  - GIS mapping platform                                            │   │
│  │  - Health monitoring                                               │   │
│  │  - Gap analysis reports                                            │   │
│  │                                                                      │   │
│  │  Benefit: Creates foundation for all future integration            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  PHASE 2 (Month 13-24): VIEWING + FEDERATION                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Implement: Model 2 + Model 3                                       │   │
│  │                                                                      │   │
│  │  Deliverables:                                                      │   │
│  │  - Unified viewing platform                                        │   │
│  │  - Middleware/federation layer                                      │   │
│  │  - VMS adapters (Milestone, Genetec, etc.)                        │   │
│  │  - ANPR metadata generation                                        │   │
│  │  - Event correlation                                               │   │
│  │                                                                      │   │
│  │  Benefit: Unified access without replacing existing systems        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  PHASE 3 (Month 25-48): CENTRAL VMS                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Implement: Model 4 (Central VMS)                                  │   │
│  │                                                                      │   │
│  │  Deliverables:                                                      │   │
│  │  - Centralized recording & storage                                 │   │
│  │  - Advanced AI analytics                                           │   │
│  │  - Database integration (VAHAN, SARTHI, eGujCop, AFIS)            │   │
│  │  - Vehicle tracking                                                │   │
│  │  - Disaster recovery                                               │   │
│  │                                                                      │   │
│  │  Benefit: Full centralized platform with advanced capabilities     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  TOTAL DURATION: 48 months (4 years)                                       │
│  TOTAL BUDGET: ₹147.5 Crore                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Approach B: Quick Win (Model 1 + Model 2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    APPROACH B: QUICK WIN                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1 (Month 1-12): REGISTRY + VIEWING                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Implement: Model 1 + Model 2                                       │   │
│  │                                                                      │   │
│  │  Deliverables:                                                      │   │
│  │  - Camera registry & GIS                                          │   │
│  │  - Unified viewing platform                                        │   │
│  │  - Basic ANPR                                                      │   │
│  │                                                                      │   │
│  │  Benefit: Quick deployment, immediate value                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  PHASE 2 (Month 13-24): ENHANCEMENT                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Implement: Model 3 (Optional)                                     │   │
│  │                                                                      │   │
│  │  Deliverables:                                                      │   │
│  │  - Middleware/federation layer                                      │   │
│  │  - Event correlation                                               │   │
│  │  - VMS adapters                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  TOTAL DURATION: 24 months (2 years)                                       │
│  TOTAL BUDGET: ₹50 Crore                                                   │
│                                                                              │
│  LIMITATION: No centralized storage, limited analytics                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Approach C: Full Centralization (Model 4 Only)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    APPROACH C: FULL CENTRALIZATION                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1 (Month 1-36): COMPLETE IMPLEMENTATION                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Implement: Model 1 + Model 4 (Full)                               │   │
│  │                                                                      │   │
│  │  Deliverables:                                                      │   │
│  │  - Camera registry & GIS                                          │   │
│  │  - Central VMS (full)                                              │   │
│  │  - Advanced analytics                                              │   │
│  │  - Database integration                                            │   │
│  │  - Vehicle tracking                                                │   │
│  │  - Disaster recovery                                               │   │
│  │                                                                      │   │
│  │  Benefit: Complete centralized solution                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  TOTAL DURATION: 36 months (3 years)                                       │
│  TOTAL BUDGET: ₹147.5 Crore                                                │
│                                                                              │
│  RISK: Higher complexity, longer timeline                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Recommended Approach

### 5.1 Recommendation: Approach A (Phased Implementation)

| Factor | Assessment |
|--------|------------|
| **Risk** | Low - Incremental delivery |
| **Cost** | Optimized - Pay as you go |
| **Timeline** | Realistic - 48 months |
| **Value** | Progressive - Benefits from Phase 1 |
| **Flexibility** | High - Can adjust between phases |
| **Scalability** | Excellent - Built-in from start |

### 5.2 Implementation Roadmap

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION ROADMAP                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  YEAR 1 (2026-2027): MODEL 1 - REGISTRY & GIS                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Q1: Database setup, core APIs                                      │   │
│  │  Q2: GIS platform development                                      │   │
│  │  Q3: Bulk import, manual entry                                     │   │
│  │  Q4: Health monitoring, gap analysis                               │   │
│  │                                                                      │   │
│  │  Milestone: All 13,000 cameras registered                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  YEAR 2 (2027-2028): MODEL 2 + MODEL 3 - VIEWING + FEDERATION             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Q1: Stream gateway development                                    │   │
│  │  Q2: VMS adapters (Milestone, Genetec)                            │   │
│  │  Q3: Unified viewing platform                                      │   │
│  │  Q4: ANPR, event correlation                                       │   │
│  │                                                                      │   │
│  │  Milestone: All departments can view feeds                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  YEAR 3-4 (2028-2030): MODEL 4 - CENTRAL VMS                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Y3 Q1-Q2: Infrastructure setup                                    │   │
│  │  Y3 Q3-Q4: Core VMS development                                   │   │
│  │  Y4 Q1-Q2: Analytics engine                                        │   │
│  │  Y4 Q3-Q4: Database integration, vehicle tracking                  │   │
│  │                                                                      │   │
│  │  Milestone: Full centralized platform operational                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Technology Integration

### 6.1 Shared Technology Components

| Component | Model 1 | Model 2 | Model 3 | Model 4 |
|-----------|---------|---------|---------|---------|
| PostgreSQL | ✓ | ✓ | ✓ | ✓ |
| Redis | ✓ | ✓ | ✓ | ✓ |
| Kafka | - | ✓ | ✓ | ✓ |
| Elasticsearch | ✓ | ✓ | ✓ | ✓ |
| React.js | ✓ | ✓ | ✓ | ✓ |
| Node.js | ✓ | ✓ | ✓ | - |
| Go | - | - | - | ✓ |
| Kubernetes | ✓ | ✓ | ✓ | ✓ |
| Docker | ✓ | ✓ | ✓ | ✓ |

### 6.2 API Integration

| API | Producer | Consumer |
|-----|----------|----------|
| Camera Registry API | Model 1 | Model 2, 3, 4 |
| Stream Gateway API | Model 2 | Model 4 |
| Event Bus API | Model 3 | Model 2, 4 |
| Analytics API | Model 4 | Model 2 |
| Database API | Model 4 | Model 2, 3 |

---

## 7. Cost Estimation

### 7.1 Approach A: Phased Implementation

| Phase | Duration | Cost (₹ Crore) |
|-------|----------|----------------|
| Phase 1: Model 1 | 12 months | 25 |
| Phase 2: Model 2 + 3 | 12 months | 45 |
| Phase 3: Model 4 | 24 months | 77.5 |
| **Total** | **48 months** | **147.5** |

### 7.2 Annual Recurring Cost

| Component | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 |
|-----------|--------|--------|--------|--------|--------|
| AMC | 5 | 10 | 15 | 20 | 25 |
| Cloud/Storage | 10 | 15 | 20 | 25 | 30 |
| Support | 5 | 8 | 12 | 15 | 18 |
| **Total** | **20** | **33** | **47** | **60** | **73** |

---

## 8. Risk Management

### 8.1 Cross-Model Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Integration complexity | High | High | Phased approach, clear interfaces |
| Data synchronization | Medium | Medium | Event-driven architecture |
| Performance issues | High | Medium | Load testing, optimization |
| Security vulnerabilities | High | Low | Security audits, penetration testing |
| Vendor lock-in | Medium | Medium | Open standards, modular design |

---

## 9. Success Criteria

### 9.1 Model-wise Success Criteria

| Model | Success Criteria |
|-------|------------------|
| **Model 1** | 100% cameras registered, GIS functional |
| **Model 2** | All departments can view feeds, ANPR working |
| **Model 3** | VMS integration complete, events correlated |
| **Model 4** | Central storage operational, analytics accurate |

### 9.2 Overall Success Criteria

| Metric | Target |
|--------|--------|
| Camera Integration | 100% (13,000+) |
| System Uptime | 99.9% |
| User Adoption | 100% departments |
| Analytics Accuracy | 95%+ |
| Alert Response Time | < 5 seconds |
| Database Integration | VAHAN, SARTHI, eGujCop, AFIS |

---

## 10. Conclusion

### 10.1 Key Takeaways

1. **Model 1 is foundational** - Must be implemented first
2. **Models 2, 3, 4 are optional** - Based on requirements and budget
3. **Phased approach recommended** - Reduces risk, provides incremental value
4. **Full integration takes 4 years** - Realistic timeline
5. **Total cost: ₹147.5 Crore** - 4-year implementation + recurring

### 10.2 Next Steps

1. **Approve Model 1 implementation** - Start immediately
2. **Plan Phase 2** - Model 2 + Model 3
3. **Budget allocation** - Secure funding for 4 years
4. **Vendor selection** - Issue RFP for Model 1
5. **Pilot project** - Start with 3-5 districts

---

*Document Version: 1.0*
*Date: September 2026*
*Combined Models Integration Architecture*