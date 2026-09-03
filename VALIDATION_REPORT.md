# Gujarat License Plate Validation Engine — Validation Report

## Overview

The Gujarat-first License Plate Validation Engine is designed for the Gujarat Police to validate and correct license plates detected by CCTV cameras across the state. The engine provides comprehensive validation, OCR error correction, and contextual analysis for all Gujarat RTO codes.

## Architecture

### Core Components

1. **RTO Database** (`GUJARAT_RTO_DATABASE.json`)
   - Contains all 40 official Gujarat RTO codes (GJ01–GJ40)
   - Includes district mapping, jurisdiction details, and active status
   - Source: Ministry of Road Transport and Highways, Government of India

2. **Validation Engine** (`licensePlateValidation.ts`)
   - Context-aware OCR correction
   - Confusable character handling
   - Invalid sequence detection
   - Impossible RTO rejection
   - Character position validation

3. **Unit Tests** (`__tests__/licensePlateValidation.test.ts`)
   - Comprehensive test coverage for all validation scenarios
   - 50+ test cases covering valid plates, OCR corrections, and edge cases

## RTO Code Coverage

### Active Gujarat RTO Codes (40 Total)

| Code | District | City | Office |
|------|----------|------|--------|
| GJ01 | Ahmedabad | Ahmedabad (West) | RTO Ahmedabad West |
| GJ02 | Mehsana | Mehsana | RTO Mehsana |
| GJ03 | Rajkot | Rajkot | RTO Rajkot |
| GJ04 | Bhavnagar | Bhavnagar | RTO Bhavnagar |
| GJ05 | Surat | Surat | RTO Surat |
| GJ06 | Vadodara | Vadodara | RTO Vadodara |
| GJ07 | Kheda | Nadiad | RTO Nadiad |
| GJ08 | Banaskantha | Palanpur | RTO Palanpur |
| GJ09 | Sabarkantha | Himmatnagar | RTO Himmatnagar |
| GJ10 | Jamnagar | Jamnagar | RTO Jamnagar |
| GJ11 | Junagadh | Junagadh | RTO Junagadh |
| GJ12 | Kutch | Bhuj | RTO Bhuj |
| GJ13 | Surendranagar | Surendranagar | ARTO Surendranagar |
| GJ14 | Amreli | Amreli | ARTO Amreli |
| GJ15 | Valsad | Valsad | RTO Valsad |
| GJ16 | Bharuch | Bharuch | ARTO Bharuch |
| GJ17 | Panchmahal | Godhra | RTO Godhra |
| GJ18 | Gandhinagar | Gandhinagar | ARTO Gandhinagar |
| GJ19 | Surat | Bardoli | ARTO Bardoli |
| GJ20 | Dahod | Dahod | ARTO Dahod |
| GJ21 | Navsari | Navsari | ARTO Navsari |
| GJ22 | Narmada | Rajpipla | ARTO Rajpipla |
| GJ23 | Anand | Anand | ARTO Anand |
| GJ24 | Patan | Patan | ARTO Patan |
| GJ25 | Porbandar | Porbandar | ARTO Porbandar |
| GJ26 | Tapi | Vyara | ARTO Vyara |
| GJ27 | Ahmedabad | Ahmedabad (East) | ARTO Ahmedabad East |
| GJ28 | Surat | Surat (West) | ARTO Surat (Pal) |
| GJ29 | Vadodara | Vadodara (Rural) | ARTO Vadodara (Darjipura) |
| GJ30 | Dang | Ahwa | ARTO Ahwa |
| GJ31 | Aravalli | Modasa | ARTO Modasa |
| GJ32 | Gir Somnath | Veraval | ARTO Veraval |
| GJ33 | Botad | Botad | ARTO Botad |
| GJ34 | Chhota Udaipur | Chhota Udaipur | ARTO Chhota Udaipur |
| GJ35 | Mahisagar | Lunawada | ARTO Lunawada |
| GJ36 | Morbi | Morbi | ARTO Morbi |
| GJ37 | Devbhoomi Dwarka | Khambhaliya | ARTO Khambhaliya |
| GJ38 | Ahmedabad | Bavla | ARTO Bavla |
| GJ39 | Kutch | Anjar | ARTO Anjar |
| GJ40 | Vav-Tharad | Tharad | ARTO Tharad |

## Validation Rules

### 1. Format Validation

**Indian Standard Format:**
```
GJ01AB1234
││││││││││
│││││││││└─ Vehicle Number (4 digits)
││││││││└── Series (2-3 letters)
│││││││└─── RTO Code (2 digits)
││││││└──── State Code (2 letters: GJ)
```

**Regex Pattern:**
```typescript
/^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$/
```

### 2. OCR Error Correction

The engine handles common OCR misreads:

| OCR Error | Correction | Context |
|-----------|------------|---------|
| `GJO1` | `GJ01` | O → 0 in RTO code |
| `GJI0` | `GJ10` | I → 1 in RTO code |
| `CJ01` | `GJ01` | C → G in state code |
| `6J01` | `GJ01` | 6 → G in state code |
| `GJ0O` | `GJ01` | O → 1 in RTO code |

### 3. Confusable Character Handling

Characters that are commonly confused by OCR systems:

| Character | Confusables | Correction Strategy |
|-----------|-------------|---------------------|
| `O` | `0, D, Q` | Context-dependent (letter vs digit position) |
| `0` | `O, D, Q` | Context-dependent |
| `I` | `1, 7, L, T` | Context-dependent |
| `1` | `I, L, 7, T` | Context-dependent |
| `L` | `1, I, 7` | Context-dependent |
| `T` | `1, I, 7, L` | Context-dependent |
| `Z` | `2, 7` | Context-dependent |
| `B` | `8, D, R` | Context-dependent |
| `S` | `5, 8` | Context-dependent |

### 4. Invalid Sequence Detection

The engine rejects invalid vehicle number sequences:

- **Repeated digits:** `0000`, `1111`, `2222`, ..., `9999`
- **Sequential digits:** `1234`, `4321`, `5678`, etc.
- **Invalid combinations:** `AAAA`, `BBBB`, etc.

### 5. Impossible RTO Rejection

The engine rejects RTO codes that:
- Don't exist in the database (e.g., `GJ99`)
- Are outside the valid range (e.g., `GJ00`, `GJ41+`)
- Have been discontinued

### 6. Character Position Validation

Each position in the license plate has strict rules:

| Position | Type | Allowed Characters | Example |
|----------|------|-------------------|---------|
| 0-1 | State Code | Letters (A-Z) | `GJ` |
| 2-3 | RTO Code | Digits (0-9) | `01` |
| 4-5 | Series | Letters (A-Z) | `AB` |
| 6-9 | Vehicle Number | Digits (0-9) | `1234` |

## Output Format

### Validation Result Structure

```typescript
interface ValidationResult {
  raw_plate: string;           // Original input
  corrected_plate: string;     // After OCR correction
  confidence: number;          // 0.0 to 1.0
  state: string;               // "Gujarat" or other state name
  district: string;            // District name
  rto_code: string;            // "GJ01" format
  registration_series: string; // "AB" format
  vehicle_number: string;      // "1234" format
  valid: boolean;              // true if valid Gujarat plate
  reason: string;              // Human-readable reason
  ocr_corrections: Array;      // List of corrections made
  validation_flags: Array;     // Warnings and errors
}
```

### Example Output

**Input:** `GJO1AB1234` (OCR error: O instead of 0)

```json
{
  "raw_plate": "GJO1AB1234",
  "corrected_plate": "GJ01AB1234",
  "confidence": 0.95,
  "state": "Gujarat",
  "district": "Ahmedabad",
  "rto_code": "GJ01",
  "registration_series": "AB",
  "vehicle_number": "1234",
  "valid": true,
  "reason": "Valid Gujarat license plate",
  "ocr_corrections": [
    {
      "position": 3,
      "original": "O",
      "corrected": "1",
      "reason": "Confusable character correction"
    }
  ],
  "validation_flags": []
}
```

**Input:** `DL01AB1234` (Delhi plate)

```json
{
  "raw_plate": "DL01AB1234",
  "corrected_plate": "DL01AB1234",
  "confidence": 0.7,
  "state": "Delhi",
  "district": "",
  "rto_code": "",
  "registration_series": "AB",
  "vehicle_number": "1234",
  "valid": false,
  "reason": "unsupported_state",
  "ocr_corrections": [],
  "validation_flags": [
    {
      "type": "unsupported_state",
      "message": "State code DL is not Gujarat",
      "severity": "info"
    }
  ]
}
```

## Confidence Scoring

The confidence score (0.0 to 1.0) is calculated based on:

1. **Base confidence:** 1.0 for clean input
2. **OCR corrections:** -0.05 per correction applied
3. **Validation errors:** -0.2 per error
4. **Validation warnings:** -0.1 per warning

**Example calculations:**
- Clean valid plate: `GJ01AB1234` → Confidence: 1.0
- One OCR correction: `GJO1AB1234` → Confidence: 0.95
- Two OCR corrections: `GJO1AB12I4` → Confidence: 0.90
- One warning: `GJ01AB1234` (sequential) → Confidence: 0.90

## API Usage

### Basic Validation

```typescript
import { validateLicensePlate } from "@sentinel/shared";

const result = validateLicensePlate("GJO1AB1234");
console.log(result.corrected_plate); // "GJ01AB1234"
console.log(result.district);        // "Ahmedabad"
console.log(result.confidence);      // 0.95
```

### Batch Validation

```typescript
import { validateMultiplePlates, calculateStats } from "@sentinel/shared";

const plates = ["GJ01AB1234", "GJO1CD5678", "DL01EF9012"];
const results = validateMultiplePlates(plates);
const stats = calculateStats(results);

console.log(stats.valid);    // 2
console.log(stats.unsupported); // 1
```

## Test Coverage

### Test Categories

1. **Valid Gujarat Plates** — All 40 RTO codes
2. **OCR Correction** — Character recovery scenarios
3. **Confusable Characters** — Letter/digit confusion
4. **Invalid RTO Rejection** — Non-existent codes
5. **Invalid Sequences** — Repeated/sequential numbers
6. **Character Position** — Position validation
7. **Unsupported States** — Non-Gujarat plates
8. **Format Validation** — Length and structure
9. **Confidence Scoring** — Score calculation
10. **Batch Operations** — Multiple plate validation
11. **Edge Cases** — Empty, short, special characters

### Running Tests

```bash
cd packages/shared
npx vitest run src/__tests__/licensePlateValidation.test.ts
```

## Performance

### Benchmarks

| Operation | Time Complexity | Space Complexity |
|-----------|-----------------|------------------|
| Single plate validation | O(1) | O(1) |
| Batch validation (n plates) | O(n) | O(n) |
| RTO lookup | O(1) | O(1) |
| Confusable correction | O(k) | O(k) |

*Where k = number of corrections (typically < 5)*

## Integration with Sentinel AI

The validation engine integrates with the existing Sentinel AI platform:

1. **CCTV Detection Pipeline**
   - License plate detected by YOLOv12 model
   - Raw OCR text passed to validation engine
   - Corrected plate used for alert generation

2. **Alert System**
   - Valid Gujarat plates trigger `LICENSE_PLATE` alerts
   - Confidence score used for alert severity
   - District information for geolocation

3. **Dashboard**
   - Real-time validation statistics
   - District-wise plate distribution
   - OCR correction frequency

## Future Enhancements

### Planned Features

1. **Historical Plate Formats**
   - Support for old format plates (e.g., `GJ-01-AB-1234`)
   - Commercial vehicle plate variations

2. **International Plates**
   - Nepal border crossing plates
   - Bhutan vehicle plates

3. **Machine Learning**
   - OCR confidence feedback loop
   - Regional dialect handling
   - Plate angle correction

4. **Performance Optimization**
   - Caching for frequent lookups
   - Bulk validation API
   - WebAssembly for edge deployment

## Data Sources

- Ministry of Road Transport and Highways, Government of India
- Gujarat Transport Department
- Parivahan Sewa (parivahan.gov.in)
- Wikipedia: List of Regional Transport Office districts in India

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-30 | Initial release with all 40 Gujarat RTO codes |

---

*Report generated for Sentinel AI — Gujarat Police CCTV Intelligence Platform*
